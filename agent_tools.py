# -*- coding: utf-8 -*-
"""
에이전트가 호출할 수 있는 도구(tool) 정의 + 실행 디스패처.

읽기 전용 도구만 존재한다 (매매/주문/파일쓰기/쉘 실행 도구는 의도적으로 없음).
각 도구 실행은 AGENT_CONFIG["per_call_timeout_seconds"]로 강제 타임아웃되고,
예외/타임아웃은 죽지 않고 {"error": "..."} 형태로 돌려줘서 에이전트가 스스로 대처하게 한다.
"""
import concurrent.futures

import yfinance as yf

from config import AGENT_CONFIG
from news_fetcher import fetch_news_headlines
from dart_fetcher import get_dart_filings as _get_dart_filings

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_with_timeout(fn, *args, **kwargs):
    timeout = AGENT_CONFIG["per_call_timeout_seconds"]
    future = _executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return {"error": f"{timeout}초 안에 응답이 없어 타임아웃됨"}
    except Exception as e:
        return {"error": str(e)}


def _get_price_impl(ticker: str) -> dict:
    df = yf.Ticker(ticker).history(period="5d")
    if df is None or df.empty:
        return {"error": "시세 데이터 없음"}
    closes = df["Close"].dropna()
    if closes.empty:
        return {"error": "시세 데이터 없음"}
    price = float(closes.iloc[-1])
    result = {"ticker": ticker, "price": round(price, 2)}
    if len(closes) >= 2:
        prev = float(closes.iloc[-2])
        if prev:
            result["daily_change_pct"] = round((price - prev) / prev * 100, 2)
    return result


def _get_news_impl(query: str, limit: int = 5) -> dict:
    headlines = fetch_news_headlines(query, limit)
    return {"query": query, "headlines": headlines}


def _get_dart_filings_impl(name: str, ticker: str, days: int = 7) -> dict:
    return _get_dart_filings(name, ticker, days=days, api_key=AGENT_CONFIG["dart_api_key"])


_REASON_PROPERTY = {
    "reason": {
        "type": "string",
        "description": "이 도구를 지금 호출하는 이유를 한 문장으로 (예: '등락률 -1.47%로 2%는 안 되지만 배당 이슈 확인 차 조사'). 로그에 그대로 남는다.",
    },
}

TOOLS = [
    {
        "name": "get_news",
        "description": "종목명(또는 검색어)으로 최근 뉴스 헤드라인을 가져온다. 구글뉴스 검색 기반.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 종목명 또는 키워드"},
                "limit": {"type": "integer", "description": "가져올 헤드라인 개수 (기본 5)"},
                **_REASON_PROPERTY,
            },
            "required": ["query", "reason"],
        },
    },
    {
        "name": "get_price",
        "description": "티커의 현재가와 전일 대비 당일 등락률(%)을 가져온다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "야후 파이낸스 티커 (예: 005930.KS, AAPL)"},
                **_REASON_PROPERTY,
            },
            "required": ["ticker", "reason"],
        },
    },
    {
        "name": "get_dart_filings",
        "description": (
            "최근 N일 내 DART(전자공시) 공시 목록을 가져온다. "
            "국내 상장 종목(.KS/.KQ)에만 적용되며, 해외 종목이나 매칭 실패 시 "
            "available=false와 함께 사유를 반환한다 (에러 아님, 정상 응답)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "회사명 (예: 삼성전자)"},
                "ticker": {"type": "string", "description": "야후 파이낸스 티커 (예: 005930.KS)"},
                "days": {"type": "integer", "description": "최근 며칠 이내 공시를 볼지 (기본 7)"},
                **_REASON_PROPERTY,
            },
            "required": ["name", "ticker", "reason"],
        },
    },
]

_DISPATCH = {
    "get_news": lambda i: _run_with_timeout(_get_news_impl, i["query"], i.get("limit", 5)),
    "get_price": lambda i: _run_with_timeout(_get_price_impl, i["ticker"]),
    "get_dart_filings": lambda i: _run_with_timeout(
        _get_dart_filings_impl, i["name"], i["ticker"], i.get("days", 7)
    ),
}


def execute_tool(name: str, tool_input: dict) -> dict:
    handler = _DISPATCH.get(name)
    if handler is None:
        return {"error": f"알 수 없는 도구: {name}"}
    return handler(tool_input)
