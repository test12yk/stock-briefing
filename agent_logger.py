# -*- coding: utf-8 -*-
"""실행별 관찰가능성 로그: 도구 호출 내역, 토큰 사용량, 호출 횟수를 JSON으로 남긴다.

Gemini 무료 티어라 비용은 기록하지 않는다(항상 $0) - 대신 토큰 수/호출 횟수로
무료 한도 대비 사용량을 가늠할 수 있게 한다.
"""
import json
import os
from datetime import datetime

from config import AGENT_CONFIG

RUNS_DIR = os.path.join(AGENT_CONFIG["log_dir"], "agent_runs")


class RunRecorder:
    def __init__(self, model: str, dry_run: bool):
        self.model = model
        self.dry_run = dry_run
        self.start_time = datetime.now()
        self.tool_calls = []
        self.iterations = 0
        self.usage_input_tokens = 0
        self.usage_output_tokens = 0
        self.api_call_count = 0
        self.mode = None  # "agent" | "fallback_rule_based"
        self.fallback_reason = None
        self.final_briefing = None

    def record_api_usage(self, input_tokens: int, output_tokens: int):
        """provider별 usage 필드 추출은 llm_client.py에서 하고, 여기엔 순수 정수만 넘긴다."""
        self.usage_input_tokens += input_tokens or 0
        self.usage_output_tokens += output_tokens or 0
        self.api_call_count += 1

    def record_tool_call(self, iteration: int, name: str, tool_input: dict, output, latency_ms: float):
        self.tool_calls.append({
            "iteration": iteration,
            "name": name,
            "input": tool_input,
            "output": output,
            "latency_ms": round(latency_ms, 1),
        })

    def finalize(self, mode: str, final_briefing: str, fallback_reason: str = None,
                 verification_warnings: list = None):
        self.mode = mode
        self.final_briefing = final_briefing
        self.fallback_reason = fallback_reason
        self.verification_warnings = verification_warnings or []

        os.makedirs(RUNS_DIR, exist_ok=True)
        duration_sec = (datetime.now() - self.start_time).total_seconds()
        record = {
            "timestamp": self.start_time.isoformat(),
            "model": self.model,
            "dry_run": self.dry_run,
            "mode": self.mode,
            "fallback_reason": self.fallback_reason,
            "verification_warnings": self.verification_warnings,
            "iterations": self.iterations,
            "tool_call_count": len(self.tool_calls),
            "api_call_count": self.api_call_count,
            "duration_seconds": round(duration_sec, 1),
            "tool_calls": self.tool_calls,
            "final_briefing": self.final_briefing,
            "usage": {
                "input_tokens": self.usage_input_tokens,
                "output_tokens": self.usage_output_tokens,
                "total_tokens": self.usage_input_tokens + self.usage_output_tokens,
            },
        }
        path = os.path.join(RUNS_DIR, f"{self.start_time:%Y-%m-%d_%H%M}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return record
