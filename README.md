# stock-briefing

실제 보유 자산(여러 증권/연금 계좌 지원)의 **평가손익**, **수익률 상/하위 종목**, **관련 뉴스**를 매일 자동으로 **카카오톡**으로 받아보는 개인 포트폴리오 브리핑 시스템입니다.

## 주요 기능

- **실제 손익 추적**: 종목별 매입단가 기반 실현/미실현 손익(%, 금액) 계산, 여러 계좌 통합 집계
- **수익률 랭킹**: 가장 많이 오르고/내린 종목을 자동으로 추려서 하이라이트
- **종목별 실시간 뉴스**: 구글 뉴스 RSS 파싱 (별도 API 키 불필요)
- **카카오톡 자동 발송**: OAuth 기반 "나에게 보내기" 연동, 토큰 자동 갱신, 200자 제한 자동 메시지 분할
- **대화형 설정 마법사**: 코드를 직접 건드리지 않고 `setup.py` 실행만으로 보유 종목/카카오 계정 등록

## 설치

```bash
pip install yfinance requests
```

## 시작하기

```bash
python3 setup.py            # 보유 종목 + 카카오 API 키를 대화형으로 입력
python3 kakao_setup.py      # 카카오 로그인 인증 (최초 1회, 위에서 카카오 키를 입력했다면)
python3 my_holdings_report.py   # 리포트 생성 + 카카오톡 발송
```

`setup.py`는 실제 터미널(대화형 입력이 되는 환경)에서 실행해야 합니다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `setup.py` | 최초 설정 마법사 — 보유 종목/카카오 API 키를 물어보고 파일 생성 |
| `my_portfolio.py` | 실제 보유 종목 데이터 (`setup.py`로 생성, `.gitignore` 처리) |
| `my_holdings_report.py` | 평가액/손익 계산 + 급등락 랭킹 + 뉴스 + 카톡 발송 |
| `config.py` | 카카오 알림 옵션, 리포트 표시 옵션(랭킹 개수 등) |
| `local_secrets.py` | 카카오 REST API 키 (`setup.py`로 생성, `.gitignore` 처리) |
| `kakao_notify.py` / `kakao_setup.py` | 카카오톡 "나에게 보내기" OAuth 연동 |
| `news_fetcher.py` | 종목별 뉴스 헤드라인 조회 |

## 카카오톡 알림 설정

1. [developers.kakao.com](https://developers.kakao.com)에서 앱 생성
2. [카카오 로그인] 활성화 → [동의항목]에서 "카카오톡 메시지 전송(talk_message)" 설정
3. [Redirect URI]에 `https://localhost:3000` 등록 (다른 값을 쓰려면 `config.py`의 `redirect_uri`도 맞춰서 수정)
4. `python3 setup.py` 실행 시 REST API 키 입력
5. `python3 kakao_setup.py` 실행 → 안내되는 URL을 브라우저에서 열어 로그인/동의 → 리다이렉트된 URL을 붙여넣기

## 실행 결과 예시

```
💼 실제 보유자산 리포트 (2026-08-25)
총평가액: 10,002,400원
손익확인 5종목 기준 - 매입 3,180,000 → 평가 10,002,400 (+6,822,400원, +214.5%)

🏆 수익률 top:
  삼성전자 +267.1% (+1,870,000원)
  ...

💧 수익률 bottom:
  TIGER KRX금현물 -0.8% (-2,300원)
  ...

📰 뉴스:
  · [삼성전자] ...
```

## 자동 실행 (cron)

```
50 11 * * 1-5 cd /path/to/stock-briefing && python3 my_holdings_report.py >> holdings_log.txt 2>&1
```

macOS에서 노트북이 잠들어 있을 시간대에 실행하려면 `pmset repeat`(정기 자동 깨우기)와 `caffeinate`(절전 방지)를 조합해서 필요한 시간에만 짧게 깨어나도록 구성할 수 있습니다.

## 여러 종목/계좌 등록하기

`setup.py`를 다시 실행하면 기존 `my_portfolio.py`를 덮어씁니다. 종목을 하나씩 추가/수정하고 싶다면 `my_portfolio.py`를 직접 열어서 편집해도 됩니다 (`my_portfolio.example.py`에 형식이 나와 있습니다).

각 항목:
```python
{'account': '계좌명', 'name': '종목명', 'ticker': '005930.KS', 'kind': '주식', 'qty': 10, 'avg_price': 70000}
```
- `avg_price`를 모르면 `None`으로 두면 평가액에는 포함되고 손익 계산에서만 제외됩니다.

## 주의사항

1. 데이터는 yfinance(무료 소스) 기준이라 실시간성이 완벽하지 않을 수 있습니다.
2. 실제 투자 판단과 책임은 본인에게 있으며, 이 도구는 참고용 자산 조회 프로그램입니다.
3. `local_secrets.py`, `my_portfolio.py`, `kakao_token.json`은 개인 자산/인증 정보를 담고 있어 `.gitignore`에 포함되어 있습니다. 이 저장소를 fork/clone해서 쓰실 때는 절대 git에 커밋하지 마세요.
