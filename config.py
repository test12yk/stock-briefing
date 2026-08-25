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
