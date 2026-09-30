# -*- coding: utf-8 -*-
"""
LLM 호출을 provider별로 감싸는 계층.

agent_briefing.py는 이 모듈의 run_tool_loop()만 알면 되고, 어떤 provider(현재 Gemini)를
쓰는지는 몰라도 된다. 나중에 Claude나 로컬 LLM(Ollama)으로 바꿀 땐 이 파일에
_run_gemini_loop()과 나란히 _run_claude_loop() 등을 추가하고 PROVIDERS에 등록하면 된다.

google-genai의 automatic function calling(SDK가 알아서 도구를 실행하고 루프를 도는 기능)은
의도적으로 비활성화한다 - 반복 횟수 제한/전체 시간 제한/도구별 로그를
우리가 직접 통제해야 하기 때문이다 (agent_briefing.py의 가드레일 요구사항).
"""
import concurrent.futures
import json
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import errors, types

from config import AGENT_CONFIG

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


@dataclass
class ToolLoopResult:
    text: str
    iterations: int
    input_tokens: int
    output_tokens: int
    # [{"iteration":i, "name":..., "input":..., "reasoning": "이 호출 직전 모델이 남긴 텍스트(있으면)"}]
    tool_call_trace: list = field(default_factory=list)


def _to_gemini_tools(tools: list) -> list:
    """agent_tools.TOOLS(provider 중립, {"name","description","input_schema"})를
    Gemini의 FunctionDeclaration 형태({"name","description","parameters"})로 변환."""
    declarations = [
        {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}
        for t in tools
    ]
    return [types.Tool(function_declarations=declarations)]


def _call_with_timeout(fn, timeout: float):
    future = _executor.submit(fn)
    return future.result(timeout=timeout)


def _extract_retry_delay_seconds(exc: errors.APIError):
    """429 응답의 details(원본 JSON)에서 RetryInfo.retryDelay를 찾아 초 단위로 반환.
    못 찾으면 None (= 재시도 근거 없음)."""
    details = getattr(exc, "details", None)
    if not details:
        return None

    def _walk(obj):
        if isinstance(obj, dict):
            if "retryDelay" in obj:
                yield obj["retryDelay"]
            for v in obj.values():
                yield from _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from _walk(v)

    for raw in _walk(details):
        # 보통 "34s" 형태의 문자열
        try:
            return float(str(raw).rstrip("s"))
        except (TypeError, ValueError):
            continue
    return None


def _is_daily_quota_error(exc: errors.APIError) -> bool:
    """일일 한도(RPD) 초과처럼 재시도해도 소용없는 429인지 문자열 휴리스틱으로 판단."""
    blob = json.dumps(getattr(exc, "details", None) or {}, ensure_ascii=False).lower()
    blob += " " + (getattr(exc, "message", "") or "").lower()
    return any(kw in blob for kw in ("perday", "per_day", "daily", "generaterequestsperday"))


def _run_gemini_loop(system_prompt, tools, user_prompt, execute_tool, recorder) -> ToolLoopResult:
    client = genai.Client(api_key=AGENT_CONFIG["gemini_api_key"])
    gemini_tools = _to_gemini_tools(tools)
    gen_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=gemini_tools,
        # SDK가 자동으로 도구를 실행/반복하지 않게 함 - 루프는 우리가 아래서 직접 돈다.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])]

    deadline = time.monotonic() + AGENT_CONFIG["max_total_seconds"]
    per_call_timeout = AGENT_CONFIG["per_call_timeout_seconds"]
    max_iterations = AGENT_CONFIG["max_iterations"]

    input_tokens = 0
    output_tokens = 0
    tool_call_trace = []

    def _generate():
        return client.models.generate_content(
            model=AGENT_CONFIG["model"], contents=contents, config=gen_config
        )

    def _call_with_rate_limit_retry():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"에이전트 전체 실행 시간({AGENT_CONFIG['max_total_seconds']}초) 초과")
        try:
            return _call_with_timeout(_generate, timeout=min(per_call_timeout, remaining))
        except errors.ClientError as e:
            if e.code != 429:
                raise
            if _is_daily_quota_error(e):
                raise RuntimeError(f"Gemini 무료 한도 초과 (일일 한도, 재시도 안 함): {e.message}") from e

            wait = _extract_retry_delay_seconds(e)
            if wait is None:
                # RPM/RPD 어느 쪽인지, 얼마나 기다려야 하는지 근거가 없으면 무작정 기다리지 않고 바로 폴백
                raise RuntimeError(f"Gemini 429 (재시도 근거 없음, 폴백): {e.message}") from e
            wait = min(wait, AGENT_CONFIG["rpm_retry_max_wait_seconds"])
            remaining = deadline - time.monotonic()
            if wait >= remaining:
                raise RuntimeError(f"Gemini 분당 한도 초과, 재시도 대기 시간이 전체 실행 제한을 넘어 포기: {e.message}") from e

            time.sleep(wait)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("재시도 대기 중 에이전트 전체 실행 시간 초과") from e
            try:
                return _call_with_timeout(_generate, timeout=min(per_call_timeout, remaining))
            except errors.ClientError as e2:
                raise RuntimeError(f"Gemini 분당 한도 초과, 재시도도 실패: {e2.message}") from e2

    for i in range(1, max_iterations + 1):
        if time.monotonic() > deadline:
            raise TimeoutError(f"에이전트 전체 실행 시간({AGENT_CONFIG['max_total_seconds']}초) 초과")

        response = _call_with_rate_limit_retry()
        usage = getattr(response, "usage_metadata", None)
        call_in = getattr(usage, "prompt_token_count", 0) or 0 if usage else 0
        call_out = getattr(usage, "candidates_token_count", 0) or 0 if usage else 0
        input_tokens += call_in
        output_tokens += call_out
        recorder.record_api_usage(input_tokens=call_in, output_tokens=call_out)
        recorder.iterations = i

        candidate = response.candidates[0]
        parts = candidate.content.parts if candidate.content else []
        function_calls = [p for p in parts if getattr(p, "function_call", None)]

        if not function_calls:
            text = "".join(p.text for p in parts if getattr(p, "text", None)).strip()
            if not text:
                raise ValueError("에이전트가 텍스트 응답을 생성하지 못함")
            return ToolLoopResult(text, i, input_tokens, output_tokens, tool_call_trace)

        contents.append(candidate.content)  # role="model" (SDK가 채워줌)
        reasoning_text = "".join(p.text for p in parts if getattr(p, "text", None)).strip()

        response_parts = []
        for part in function_calls:
            fc = part.function_call
            tool_input = dict(fc.args) if fc.args else {}
            t0 = time.monotonic()
            output = execute_tool(fc.name, tool_input)
            latency_ms = (time.monotonic() - t0) * 1000
            recorder.record_tool_call(i, fc.name, tool_input, output, latency_ms)
            tool_call_trace.append({
                "iteration": i, "name": fc.name, "input": tool_input, "reasoning": reasoning_text,
            })
            response_parts.append(
                types.Part.from_function_response(name=fc.name, response={"result": output})
            )
        # Gemini는 함수 응답도 role="user"로 돌려받는다 ("tool" role은 400 INVALID_ARGUMENT).
        contents.append(types.Content(role="user", parts=response_parts))

    # 10회 넘도록 함수 호출이 계속되면: tools 없이 1회 더 호출해서 강제로 텍스트 마감
    recorder.iterations = max_iterations + 1
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(
            text="이제 도구를 더 호출하지 말고, 지금까지 조사한 내용만으로 브리핑을 마무리해서 작성하세요."
        )],
    ))
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(f"에이전트 전체 실행 시간({AGENT_CONFIG['max_total_seconds']}초) 초과")
    final_config = types.GenerateContentConfig(system_instruction=system_prompt)  # tools 없이
    response = _call_with_timeout(
        lambda: client.models.generate_content(model=AGENT_CONFIG["model"], contents=contents, config=final_config),
        timeout=min(per_call_timeout, remaining),
    )
    usage = getattr(response, "usage_metadata", None)
    call_in = getattr(usage, "prompt_token_count", 0) or 0 if usage else 0
    call_out = getattr(usage, "candidates_token_count", 0) or 0 if usage else 0
    input_tokens += call_in
    output_tokens += call_out
    recorder.record_api_usage(input_tokens=call_in, output_tokens=call_out)
    parts = response.candidates[0].content.parts if response.candidates[0].content else []
    text = "".join(p.text for p in parts if getattr(p, "text", None)).strip()
    if not text:
        raise ValueError("에이전트가 강제 마감 후에도 텍스트 응답을 생성하지 못함")
    return ToolLoopResult(text, max_iterations + 1, input_tokens, output_tokens, tool_call_trace)


_PROVIDERS = {
    "gemini": _run_gemini_loop,
}


def run_tool_loop(system_prompt: str, tools: list, user_prompt: str, execute_tool, recorder) -> ToolLoopResult:
    provider = AGENT_CONFIG["provider"]
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise RuntimeError(f"지원하지 않는 LLM provider: {provider}")
    return fn(system_prompt, tools, user_prompt, execute_tool, recorder)
