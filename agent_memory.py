# -*- coding: utf-8 -*-
"""최근 N일치 브리핑을 파일로 저장/로드 (에이전트의 단기 메모리)."""
import os
from datetime import datetime, timedelta

from config import AGENT_CONFIG

HISTORY_DIR = os.path.join(AGENT_CONFIG["log_dir"], "briefing_history")
TEST_RUNS_DIR = os.path.join(AGENT_CONFIG["log_dir"], "test_runs")


def save_briefing(text: str, date: datetime = None):
    """실제 운영 실행(카카오 발송) 결과만 여기 저장 - 다음날 메모리로 참고됨."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    date = date or datetime.now()
    path = os.path.join(HISTORY_DIR, f"{date:%Y-%m-%d}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def save_test_run(text: str, timestamp: datetime = None):
    """--dry-run 등 테스트/개발용 실행 결과. 메모리(load_recent_briefings)에는 절대 반영되지 않음."""
    os.makedirs(TEST_RUNS_DIR, exist_ok=True)
    timestamp = timestamp or datetime.now()
    path = os.path.join(TEST_RUNS_DIR, f"{timestamp:%Y-%m-%d_%H%M%S}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_recent_briefings(days: int = None) -> list:
    """최근 N일치 (오늘 제외) 브리핑을 날짜 오래된 순으로 반환. [{"date": "...", "text": "..."}]"""
    days = days if days is not None else AGENT_CONFIG["memory_days"]
    if not os.path.isdir(HISTORY_DIR):
        return []

    results = []
    today = datetime.now().date()
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        path = os.path.join(HISTORY_DIR, f"{d:%Y-%m-%d}.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                results.append({"date": f"{d:%Y-%m-%d}", "text": f.read()})
    results.reverse()  # 오래된 순
    return results
