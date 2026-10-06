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
    from local_secrets import DART_API_KEY
except ImportError:
    DART_API_KEY = None

try:
    from local_secrets import DIVIDEND_KAKAO_REST_API_KEY
except ImportError:
    DIVIDEND_KAKAO_REST_API_KEY = None

try:
    from local_secrets import DIVIDEND_KAKAO_CLIENT_SECRET
except ImportError:
    DIVIDEND_KAKAO_CLIENT_SECRET = None

KAKAO_CONFIG = {
    "enabled": bool(KAKAO_REST_API_KEY),        # local_secrets.py가 없으면 자동으로 꺼짐
    "rest_api_key": KAKAO_REST_API_KEY,
    "redirect_uri": "https://localhost:3000",   # 카카오 로그인 설정에 등록한 Redirect URI와 동일해야 함
    "news_per_ticker": 2,                       # 보유 종목당 첨부할 뉴스 헤드라인 개수
}

# dividend_bot.py 전용 카카오 앱. my_holdings_report.py와 같은 앱(KAKAO_CONFIG)을 쓰면
# 카카오톡 메시지에 뜨는 "APP OOO" 발신 앱 라벨이 똑같이 떠서 구별이 안 되므로,
# developers.kakao.com에 별도 앱을 하나 더 만들어 여기 연결한다 (설정법은 README 참고).
DIVIDEND_KAKAO_CONFIG = {
    "enabled": bool(DIVIDEND_KAKAO_REST_API_KEY),
    "rest_api_key": DIVIDEND_KAKAO_REST_API_KEY,
    # 이 앱은 "클라이언트 시크릿" 보안 기능이 켜져 있어서 토큰 발급/갱신 요청에 같이 보내야 함
    # (카카오 로그인 콘솔: 앱 > 플랫폼 키 > REST API 키 > 클라이언트 시크릿)
    "client_secret": DIVIDEND_KAKAO_CLIENT_SECRET,
    "redirect_uri": "https://localhost:3000",
}

MY_HOLDINGS_CONFIG = {
    "top_movers_count": 3,       # 수익률 상/하위 각각 몇 종목씩 보여줄지
    "news_for_movers": 1,        # 상/하위 종목당 첨부할 뉴스 헤드라인 개수
}

DIVIDEND_CONFIG = {
    "enabled": bool(DART_API_KEY),
    "dart_api_key": DART_API_KEY,
    # 배당소득세(지방소득세 포함) - 일반 위탁계좌에서 즉시 원천징수되는 비율
    "tax_rate": 0.154,
    # 이 계좌들은 배당소득세가 즉시 징수되지 않고 계좌 내에서 과세이연됨
    # (ISA: 만기시 손익통산 후 분리과세, 연금계좌: 인출시 연금소득세) → 입금 시점 세후 = 세전
    "tax_deferred_accounts": {"ISA", "연금계좌1", "연금계좌2"},
    "dart_lookback_days": 5,     # DART 개별주식 배당결정 공시 조회 기간(최근 N일)
    "kind_lookback_days": 10,    # KIND ETF 분배금 일괄공시 조회 기간(최근 N일, 주기가 더 뜸해서 더 길게)
}
