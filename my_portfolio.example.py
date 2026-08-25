# -*- coding: utf-8 -*-
"""
my_portfolio.py 템플릿 (가짜 예시 데이터).
이 파일을 my_portfolio.py로 복사한 뒤, 실제 보유 종목으로 채워 넣으세요.
    cp my_portfolio.example.py my_portfolio.py
my_portfolio.py는 .gitignore에 포함되어 있어 git에 올라가지 않습니다.

각 항목:
  account: 계좌 구분(원하는 이름으로 자유롭게, 예: "ISA", "일반계좌")
  name: 종목명 (뉴스 검색어로도 사용됨)
  ticker: 야후 파이낸스 티커 (한국은 .KS/.KQ 접미사 필요)
  kind: "주식" 또는 "ETF"
  qty: 보유 수량
  avg_price: 매입단가(원). 모르면 None으로 두면 평가액엔 포함되고 손익 계산에서는 제외됨
"""
MY_HOLDINGS = [
    {'account': 'ISA', 'name': '삼성전자', 'ticker': '005930.KS', 'kind': '주식', 'qty': 10, 'avg_price': 70000},
    {'account': 'ISA', 'name': 'SK하이닉스', 'ticker': '000660.KS', 'kind': '주식', 'qty': 3, 'avg_price': 150000},
    {'account': 'ISA', 'name': 'TIGER 미국S&P500', 'ticker': '360750.KS', 'kind': 'ETF', 'qty': 50, 'avg_price': 20000},
    {'account': '연금계좌', 'name': 'KODEX 미국나스닥100', 'ticker': '379810.KS', 'kind': 'ETF', 'qty': 30, 'avg_price': 25000},
    {'account': '연금계좌', 'name': 'TIGER KRX금현물', 'ticker': '0072R0.KS', 'kind': 'ETF', 'qty': 20, 'avg_price': 14000},
]
