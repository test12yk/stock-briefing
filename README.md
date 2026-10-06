# stock-briefing

실제 보유 자산(여러 증권/연금 계좌 지원)의 **평가손익**, **수익률 상/하위 종목**, **관련 뉴스**를 매일 자동으로 **카카오톡**으로 받아보는 개인 포트폴리오 브리핑 시스템입니다.

## 주요 기능

- **실제 손익 추적**: 종목별 매입단가 기반 실현/미실현 손익(%, 금액) 계산, 여러 계좌 통합 집계
- **수익률 랭킹**: 가장 많이 오르고/내린 종목을 자동으로 추려서 하이라이트
- **종목별 실시간 뉴스**: 구글 뉴스 RSS 파싱 (별도 API 키 불필요)
- **카카오톡 자동 발송**: OAuth 기반 "나에게 보내기" 연동, 토큰 자동 갱신, 200자 제한 자동 메시지 분할
- **대화형 설정 마법사**: 코드를 직접 건드리지 않고 `setup.py` 실행만으로 보유 종목/카카오 계정 등록
- **배당/분배금 공시 알림** (`dividend_bot.py`): 보유 종목의 배당 공시가 뜨면 보유수량 기준 예상 입금액(계좌별 세전/세후)을 카카오톡으로 알려줌

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
| `dividend_bot.py` | 보유 종목 배당/분배금 공시 감지 + 예상 입금액 계산 + 카톡 발송 |

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

## 배당/분배금 공시 알림 (`dividend_bot.py`)

보유 종목(`my_portfolio.py`)의 배당 소식이 공시되면, 보유수량을 곱한 예상 입금액(계좌별 세전/세후)을 카카오톡으로 알려줍니다.

- **개별 주식**: DART(전자공시시스템)의 "현금ㆍ현물배당결정" 공시를 조회해서 1주당 배당금/배당기준일/지급예정일을 공시 원문에서 직접 파싱합니다. (`local_secrets.py`에 `DART_API_KEY` 필요 — [opendart.fss.or.kr](https://opendart.fss.or.kr)에서 무료 발급)
- **ETF**: ETF는 DART 공시 대상이 아니라서, 한국거래소 KIND 상장공시시스템의 "ETF이익금분배신고(분배금안내)" 일괄공시를 조회해서 보유 ETF명과 일치하는 분배금만 추려냅니다.
- **세전/세후**: ISA·연금계좌는 입금 시점에 배당소득세가 즉시 징수되지 않고 계좌 내에서 과세이연되므로 세후=세전으로 표시하고, 일반 위탁계좌(일반종합/토스증권)만 배당소득세 15.4%를 적용합니다.
- 이미 알려준 공시는 `dividend_state.json`에 접수번호로 기록해서 중복 알림을 보내지 않습니다.
- 해외주식(토스증권의 미국주식)은 이 두 데이터소스 어디에도 해당하지 않아 현재는 알림 대상에서 제외됩니다.
- 메시지 맨 앞줄은 "💰 배당·분배금 공시 알림"로 시작해서 `my_holdings_report.py`의 "💼 실제 보유자산 리포트"와 한눈에 구별됩니다. 하루에 여러 건이 감지돼도 한 메시지(다이제스트)로 묶어서 보냅니다.

```bash
python3 dividend_bot.py          # 공시 확인 + 있으면 카톡 발송
python3 dividend_bot.py --test   # 발송/상태저장 없이 콘솔 출력만 (점검용)
```

### 배당봇 전용 카카오 앱 설정

`my_holdings_report.py`와 같은 카카오 앱(REST API 키)을 쓰면 카카오톡 메시지 하단에 뜨는 "APP OOO" 발신 앱 라벨까지는 구별이 안 됩니다 (메시지 내용이 아니라 앱 자체에 달린 라벨이라 메시지 payload로 바꿀 수 없음). 이 라벨까지 다르게 보이게 하려면 배당봇 전용 카카오 앱을 하나 더 만드세요 (stock-bot/stock-briefing 사이에서도 이미 같은 이유로 `kakao_notify.py`/`kakao_setup.py`가 저장소별로 복제되어 있습니다).

1. [developers.kakao.com](https://developers.kakao.com) → 내 애플리케이션 → 애플리케이션 추가하기 (앱 이름: 원하는 대로, 예: "배당알림봇")
2. [앱 키] → **REST API 키** 복사
3. [카카오 로그인] 활성화 → [동의항목]에서 "카카오톡 메시지 전송(talk_message)" 설정
4. [카카오 로그인] → [Redirect URI]에 `https://localhost:3000` 등록
5. `local_secrets.py`에 한 줄 추가:
   ```python
   DIVIDEND_KAKAO_REST_API_KEY = "여기에 2번에서 복사한 REST API 키"
   ```
6. `python3 dividend_kakao_setup.py` 실행 → 안내되는 URL을 브라우저에서 열어 로그인/동의 → 리다이렉트된 URL을 붙여넣기 (`dividend_kakao_token.json` 생성됨, `kakao_token.json`과 별개 파일)

이 설정 전까지는 `dividend_bot.py`를 `--test` 없이 실행하면 카톡 발송 전에 바로 에러로 막힙니다.

## 자동 실행 (cron)

```
50 11 * * 1-5 cd /path/to/stock-briefing && python3 my_holdings_report.py >> holdings_log.txt 2>&1
0  14 * * 1-5 cd /path/to/stock-briefing && python3 dividend_bot.py >> dividend_log.txt 2>&1
```

macOS에서 노트북이 잠들어 있을 시간대에 실행하려면 `pmset repeat`(정기 자동 깨우기)와 `caffeinate`(절전 방지)를 조합해서 필요한 시간에만 짧게 깨어나도록 구성할 수 있습니다. `dividend_bot.py`는 긴급성이 낮은 작업이라(공시가 며칠 늦게 감지돼도 무방), 새 깨우기 시간을 따로 만들지 않고 이미 안정적으로 동작 중인 다른 작업의 깨어있는 시간대에 붙여서 실행하는 걸 추천합니다.

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
