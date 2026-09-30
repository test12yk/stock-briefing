# -*- coding: utf-8 -*-
"""
설정 파일. 카카오 알림 옵션과 리포트 표시 옵션만 담고 있습니다.
API 키는 local_secrets.py, 보유 종목은 my_portfolio.py에서 관리합니다
(둘 다 setup.py를 실행하면 대화형으로 생성됩니다).
"""

try:
    from local_secrets import KAKAO_REST_API_KEY
except ImportError:
    KAKAO_REST_API_KEY = None

try:
    from local_secrets import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = None

try:
    from local_secrets import DART_API_KEY
except ImportError:
    DART_API_KEY = None

KAKAO_CONFIG = {
    "enabled": bool(KAKAO_REST_API_KEY),        # local_secrets.py가 없으면 자동으로 꺼짐
    "rest_api_key": KAKAO_REST_API_KEY,
    "redirect_uri": "https://localhost:3000",   # 카카오 로그인 설정에 등록한 Redirect URI와 동일해야 함
    "news_per_ticker": 2,                       # 보유 종목당 첨부할 뉴스 헤드라인 개수
}

MY_HOLDINGS_CONFIG = {
    "top_movers_count": 3,       # 수익률 상/하위 각각 몇 종목씩 보여줄지
    "news_for_movers": 1,        # 상/하위 종목당 첨부할 뉴스 헤드라인 개수
}

# 에이전트(agent_briefing.py) 설정.
# GEMINI_API_KEY가 없으면 agent_briefing.py는 규칙 기반(my_holdings_report.py와 동일 로직)으로
# 자동 폴백합니다 - 카카오 발송 자체는 키 유무와 무관하게 항상 이루어집니다.
# LLM 호출은 llm_client.py를 거치므로, 나중에 provider를 바꿀 때도 이 파일만 손보면 됩니다.
AGENT_CONFIG = {
    "enabled": bool(GEMINI_API_KEY),
    "provider": "gemini",
    "gemini_api_key": GEMINI_API_KEY,
    "dart_api_key": DART_API_KEY,             # 없으면 get_dart_filings 툴이 비활성화됨(DART 대상 아님으로 응답)
    # gemini-3.5-flash-lite: 무료 티어 일일 한도가 flash 계열 중 가장 넉넉함(~500 RPD vs flash ~20 RPD).
    # 원인 분석 품질이 아쉬우면 "gemini-3.5-flash"로 바꿔서 비교 가능 (한도는 훨씬 낮아짐).
    "model": "gemini-3.5-flash-lite",
    "max_iterations": 10,                     # tool 호출 루프 최대 반복 횟수
    "max_total_seconds": 180,                 # 에이전트 전체 실행 시간 제한(3분) - 초과 시 폴백
    "per_call_timeout_seconds": 30,           # API 호출/도구 호출 1건당 타임아웃
    "rpm_retry_max_wait_seconds": 60,         # 분당 한도(429) 초과 시 최대 이만큼만 기다렸다가 1회 재시도
    "memory_days": 3,                         # 최근 며칠치 브리핑을 컨텍스트로 참고할지
    "log_dir": "logs",                        # logs/agent_runs, logs/briefing_history 하위에 생성
}
