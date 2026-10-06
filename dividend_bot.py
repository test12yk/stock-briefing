# -*- coding: utf-8 -*-
"""
보유 종목(my_portfolio.py)의 배당/분배금 공시를 감지해서 카카오톡 "나에게 보내기"로
예상 입금액(세전/세후, 계좌별)을 알려주는 봇.

- 개별 주식: DART(전자공시시스템)의 "현금ㆍ현물배당결정" 수시공시를 종목별로 조회해서
  1주당 배당금 / 배당기준일 / 배당금지급 예정일자를 공시 원문에서 직접 파싱한다.
- ETF: 개별 주식과 달리 DART 공시 대상이 아니므로, 한국거래소 KIND 상장공시시스템의
  "ETF이익금분배신고(분배금안내)" 공시(자산운용사의 사무관리사가 운용 ETF 전체를 묶어
  한 번에 공시하는 일괄공시)를 조회해서 보유 ETF명과 정확히 일치하는 행만 추려낸다.

이미 처리한 공시는 dividend_state.json에 접수번호로 기록해두고 건너뛴다 (중복 알림 방지).
개별 주식의 corp_code는 매번 DART의 전체 기업 코드 목록(CORPCODE.xml, 하루 캐시)에서
my_portfolio.py에 있는 티커를 찾아 동적으로 매핑한다 - 보유 종목이 바뀌어도 이 파일을
따로 손댈 필요가 없다. 우선주처럼 CORPCODE.xml에 별도 매핑이 없는 종목은
PREFERRED_SHARE_OVERRIDES에서 보통주 corp_code + 공시상 종류주식명으로 수동 매핑한다.

사용법:
    python3 dividend_bot.py          # 공시 확인 후 있으면 카카오톡 발송 + 상태 저장
    python3 dividend_bot.py --test   # 카카오톡 발송/상태 저장 없이 콘솔에만 출력 (점검용)

크론 등록 예) 30 17 * * 1-5 cd /path/to/stock-briefing && python3 dividend_bot.py >> dividend_log.txt 2>&1
"""
import io
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta

import requests

from config import DIVIDEND_CONFIG
from kakao_notify import send_kakao_message

try:
    from my_portfolio import MY_HOLDINGS
except ImportError:
    raise SystemExit(
        "my_portfolio.py가 없습니다. my_portfolio.example.py를 복사해서 실제 보유 종목으로 채워 넣으세요."
    )

STATE_FILE = "dividend_state.json"
CORP_CODE_CACHE_FILE = "dart_corp_code_cache.json"
CORP_CODE_CACHE_MAX_AGE_DAYS = 30

# CORPCODE.xml에 자체 종목코드가 없는 종목(대부분 우선주)을 위한 수동 매핑.
# common_ticker: 같은 회사 보통주 티커(my_portfolio.py 표기와 동일하게 .KS/.KQ 포함) → 그 corp_code로 공시 조회
# class_name: 공시 원문 "종류주식에 대한 배당 관련 사항" 표의 종류주식명.
#   주의: 이 이름은 KRX 상장 티커명(예: "현대차2우B")이 아니라 DART 내부 표기(예: "2우선주")를 써야 함 -
#   실제 공시 원문으로 확인한 값. 다른 우선주 보유 종목을 추가할 때도 공시를 열어서 직접 확인할 것.
PREFERRED_SHARE_OVERRIDES = {
    "005387.KS": {"common_ticker": "005380.KS", "class_name": "2우선주"},
}


# ───────────────────────── 공통 유틸 ─────────────────────────

def _flatten_tags(html_text: str) -> list:
    """HTML 태그를 구분자로 바꾸고 빈 셀을 제거해서 '본문 토큰' 리스트로 만든다.
    DART/KIND 공시 원문이 전부 고정 양식의 표라서, 태그만 벗겨내면
    [레이블, 레이블, ..., 값, 값, ...] 형태의 토큰 시퀀스로 안정적으로 파싱할 수 있다."""
    text = re.sub(r"<[^>]+>", "|", html_text)
    text = re.sub(r"&amp;", "&", text)
    tokens = [t.strip() for t in text.split("|")]
    return [t for t in tokens if t]


def _find_next_after(tokens: list, label_substr: str, offset: int = 1):
    """tokens에서 label_substr을 포함하는 첫 토큰을 찾아 그 offset번째 다음 토큰을 반환."""
    for i, t in enumerate(tokens):
        if label_substr in t:
            if i + offset < len(tokens):
                return tokens[i + offset]
            return None
    return None


def _to_amount(s: str):
    """'374', '1,420', '559.48', '-' 같은 문자열을 숫자(원화)로 변환. 소수점이 있으면 float,
    없으면 int로 반환하고 파싱 불가하면 None. ('-'는 "해당 없음"이라 None, '0'은 실제 0원)"""
    if not s:
        return None
    s = s.replace(",", "").strip()
    if s == "-" or s == "":
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return None


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"dart_seen": [], "kind_seen": []}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("dart_seen", [])
    state.setdefault("kind_seen", [])
    return state


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ───────────────────────── 보유 종목 인덱싱 ─────────────────────────

def build_holdings_index():
    """my_portfolio.py를 종목별로 재구성한다.
    stock_positions: {ticker: [{'account', 'qty'}, ...]} - 국내 개별 주식만 (해외주식은 DART 대상 아님)
    etf_positions:   {종목명: [{'account', 'qty', 'ticker'}, ...]} - ETF 전체
    """
    stock_positions = defaultdict(list)
    etf_positions = defaultdict(list)
    for h in MY_HOLDINGS:
        if h.get("currency") == "USD":
            continue  # 해외주식은 DART/KIND 대상이 아님 (추후 별도 소스 필요)
        entry = {"account": h["account"], "qty": h["qty"]}
        if h["kind"] == "주식":
            stock_positions[h["ticker"]].append(entry)
        elif h["kind"] == "ETF":
            entry["ticker"] = h["ticker"]
            etf_positions[h["name"]].append(entry)
    return stock_positions, etf_positions


def calc_amounts(per_share, positions: list) -> list:
    """계좌별로 (계좌명, 수량, 세전, 세후, 과세이연여부)를 계산.
    per_share가 소수(분기배당 비례계산 등)여도 실제 입금액은 원 단위이므로 반올림한다."""
    deferred_accounts = DIVIDEND_CONFIG["tax_deferred_accounts"]
    tax_rate = DIVIDEND_CONFIG["tax_rate"]
    results = []
    for pos in positions:
        qty = pos["qty"]
        pretax = round(per_share * qty)
        is_deferred = pos["account"] in deferred_accounts
        posttax = pretax if is_deferred else round(pretax * (1 - tax_rate))
        results.append({
            "account": pos["account"], "qty": qty,
            "pretax": pretax, "posttax": posttax, "deferred": is_deferred,
        })
    return results


# ───────────────────────── DART (개별 주식) ─────────────────────────

def get_corp_code_map() -> dict:
    """{6자리 종목코드: corp_code} 매핑을 반환. 로컬에 30일 캐시."""
    if os.path.exists(CORP_CODE_CACHE_FILE):
        age_days = (datetime.now().timestamp() - os.path.getmtime(CORP_CODE_CACHE_FILE)) / 86400
        if age_days < CORP_CODE_CACHE_MAX_AGE_DAYS:
            with open(CORP_CODE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)

    resp = requests.get(
        "https://opendart.fss.or.kr/api/corpCode.xml",
        params={"crtfc_key": DIVIDEND_CONFIG["dart_api_key"]},
        timeout=20,
    )
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])

    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_bytes)
    mapping = {}
    for corp in root.findall("list"):
        stock_code = (corp.findtext("stock_code") or "").strip()
        if stock_code:
            mapping[stock_code] = corp.findtext("corp_code")

    with open(CORP_CODE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False)
    return mapping


def resolve_corp_codes(stock_positions: dict, corp_code_map: dict) -> dict:
    """{ticker: {'corp_code', 'class_name' or None}} - DART 조회에 쓸 매핑.
    class_name이 있으면 보통주가 아니라 특정 종류주식(우선주)의 1주당 배당금을 찾아야 함."""
    resolved = {}
    for ticker in stock_positions:
        if ticker in PREFERRED_SHARE_OVERRIDES:
            override = PREFERRED_SHARE_OVERRIDES[ticker]
            corp_code = corp_code_map.get(override["common_ticker"].split(".")[0])
            if corp_code:
                resolved[ticker] = {"corp_code": corp_code, "class_name": override["class_name"]}
            continue
        code6 = ticker.split(".")[0]
        corp_code = corp_code_map.get(code6)
        if corp_code:
            resolved[ticker] = {"corp_code": corp_code, "class_name": None}
        else:
            print(f"  ⚠ DART corp_code를 찾지 못함 (매핑 필요): {ticker}")
    return resolved


def _is_dividend_decision_report(report_nm: str) -> bool:
    return "배당결정" in report_nm and "배당을위한" not in report_nm


def fetch_dart_dividend_filings(corp_code: str, lookback_days: int) -> list:
    end = datetime.now()
    begin = end - timedelta(days=lookback_days)
    resp = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={
            "crtfc_key": DIVIDEND_CONFIG["dart_api_key"],
            "corp_code": corp_code,
            "bgn_de": begin.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_count": 100,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "000":
        return []
    return [it for it in data.get("list", []) if _is_dividend_decision_report(it["report_nm"])]


def parse_dart_dividend_doc(rcept_no: str) -> dict:
    """공시 원문(document.xml)에서 보통주 1주당 배당금, 종류주식별 1주당 배당금,
    배당기준일, 배당금지급 예정일자를 추출."""
    resp = requests.get(
        "https://opendart.fss.or.kr/api/document.xml",
        params={"crtfc_key": DIVIDEND_CONFIG["dart_api_key"], "rcept_no": rcept_no},
        timeout=15,
    )
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        html_bytes = zf.read(zf.namelist()[0])
    tokens = _flatten_tags(html_bytes.decode("utf-8", errors="replace"))

    common_amount = _to_amount(_find_next_after(tokens, "1주당 배당금", offset=2))
    record_date = _find_next_after(tokens, "배당기준일")
    pay_date = _find_next_after(tokens, "배당금지급 예정일자")

    # 종류주식(우선주)별 1주당 배당금: "【종류주식에 대한 배당 관련 사항】" 표 마커 뒤에
    # 헤더 5칸(종류주식명/구분/1주당배당금/시가배당률/배당금총액) + 데이터 5칸씩 반복되는 구조.
    # 종류주식명은 DART 내부 표기(예: "우선주"=1종, "2우선주", "3우선주")라 KRX 티커명과 다를 수 있음.
    class_amounts = {}
    for i, t in enumerate(tokens):
        if "종류주식에 대한 배당" in t:
            rows = tokens[i + 1 + 5:]  # 마커 다음 헤더 5칸을 건너뛰고 데이터부터
            for j in range(0, len(rows) - 4, 5):
                name, _gubun, amount_s = rows[j], rows[j + 1], rows[j + 2]
                amount = _to_amount(amount_s)
                if amount is None:
                    break  # 표가 끝나고 다른 섹션(기타 투자판단 등)으로 넘어간 지점
                class_amounts[name] = amount
            break

    return {
        "common_amount": common_amount,
        "class_amounts": class_amounts,
        "record_date": record_date,
        "pay_date": pay_date,
    }


def check_dart_dividends(stock_positions: dict, state: dict) -> list:
    notifications = []
    corp_code_map = get_corp_code_map()
    resolved = resolve_corp_codes(stock_positions, corp_code_map)

    # 같은 corp_code를 여러 티커가 공유할 수 있음(보통주+우선주) → corp_code 기준으로 한 번만 공시 조회
    by_corp_code = defaultdict(list)
    for ticker, info in resolved.items():
        by_corp_code[info["corp_code"]].append((ticker, info["class_name"]))

    for corp_code, ticker_infos in by_corp_code.items():
        try:
            filings = fetch_dart_dividend_filings(corp_code, DIVIDEND_CONFIG["dart_lookback_days"])
        except Exception as e:
            print(f"  ⚠ DART 공시 목록 조회 실패 (corp_code={corp_code}): {e}")
            continue

        for filing in filings:
            rcept_no = filing["rcept_no"]
            if rcept_no in state["dart_seen"]:
                continue
            try:
                parsed = parse_dart_dividend_doc(rcept_no)
            except Exception as e:
                print(f"  ⚠ DART 공시 원문 파싱 실패 ({rcept_no}): {e}")
                continue

            for ticker, class_name in ticker_infos:
                per_share = (
                    parsed["class_amounts"].get(class_name)
                    if class_name else parsed["common_amount"]
                )
                if per_share is None:
                    print(f"  ⚠ {filing['corp_name']}({ticker}) 1주당 배당금 파싱 실패 - 공시 확인 필요 (rcept_no={rcept_no})")
                    continue
                amounts = calc_amounts(per_share, stock_positions[ticker])
                notifications.append({
                    "name": filing["corp_name"] + (f" ({class_name})" if class_name else ""),
                    "per_share": per_share,
                    "record_date": parsed["record_date"],
                    "pay_date": parsed["pay_date"],
                    "amounts": amounts,
                })
            state["dart_seen"].append(rcept_no)

    return notifications


# ───────────────────────── KIND (ETF 분배금) ─────────────────────────

_KIND_BASE = "https://kind.krx.co.kr"


def _kind_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": _KIND_BASE + "/"})
    s.get(f"{_KIND_BASE}/disclosure/disclosurebystocktype.do",
          params={"method": "searchDisclosureByStockTypeEtf"}, timeout=15)
    return s


def search_kind_distribution_filings(session: requests.Session, lookback_days: int) -> list:
    """ETF 분배금 일괄공시 목록을 (acptno, rcept_dt, title) 리스트로 반환."""
    end = datetime.now()
    begin = end - timedelta(days=lookback_days)
    data = {
        "method": "searchDisclosureByStockTypeEtfSub",
        "forward": "disclosurebystocktype_etf_sub",
        "currentPageSize": "100",
        "pageIndex": "1",
        "orderMode": "0",
        "orderStat": "D",
        "fromDate": begin.strftime("%Y-%m-%d"),
        "toDate": end.strftime("%Y-%m-%d"),
        "etfIsuSrtCd": "",
        "etfIsuSrtNm": "",
        "reportNm": "분배금",
    }
    resp = session.post(f"{_KIND_BASE}/disclosure/disclosurebystocktype.do", data=data, timeout=20)
    resp.raise_for_status()
    rows = []
    seen_in_page = set()
    for m in re.finditer(r"onclick=\"openDisclsViewer\('(\d+)','(\d*)'\)\"[^>]*title='([^']+)'", resp.text):
        acptno, _docno, title = m.groups()
        if "분배금" not in title:
            continue
        if acptno in seen_in_page:
            continue
        seen_in_page.add(acptno)
        rows.append({"acptno": acptno, "title": title})
    return rows


def resolve_kind_doc_url(session: requests.Session, acptno: str) -> str:
    """일괄공시 접수번호로 실제 분배금 표가 들어있는 문서의 htm URL을 찾는다."""
    session.get(f"{_KIND_BASE}/common/disclsviewer.do",
                params={"method": "searchHostAddrOfDisclsViewer", "acptno": acptno, "docno": ""},
                timeout=15)
    viewer_resp = session.get(
        f"{_KIND_BASE}/common/disclsviewer.do",
        params={"method": "search", "acptno": acptno, "docno": "", "viewerhost": "kind.krx.co.kr", "viewerport": ""},
        timeout=15,
    )
    m = re.search(r"<option value='(\d+)\|[YN]'\s*selected", viewer_resp.text)
    if not m:
        raise RuntimeError(f"mainDoc docNo를 찾지 못함 (acptno={acptno})")
    doc_no = m.group(1)

    contents_resp = session.get(
        f"{_KIND_BASE}/common/disclsviewer.do",
        params={"method": "searchContents", "docNo": doc_no},
        timeout=15,
    )
    m2 = re.search(r"parent\.setPath\('[^']*','([^']+)'", contents_resp.text)
    if not m2:
        raise RuntimeError(f"문서 경로를 찾지 못함 (acptno={acptno}, docNo={doc_no})")
    return m2.group(1)


def parse_kind_distribution_table(html_text: str) -> list:
    """[{'isin','name','record_date','pay_date','amount'}, ...] 형태로 분배금 표를 파싱."""
    tokens = _flatten_tags(html_text)
    rows = []
    isin_re = re.compile(r"^KR7[0-9A-Z]{9}$")
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    i = 0
    while i < len(tokens):
        if isin_re.match(tokens[i]) and i + 4 < len(tokens):
            name = tokens[i + 1]
            record_date = tokens[i + 2] if date_re.match(tokens[i + 2]) else None
            pay_date = tokens[i + 3] if date_re.match(tokens[i + 3]) else None
            amount = _to_amount(tokens[i + 4])
            rows.append({"isin": tokens[i], "name": name, "record_date": record_date,
                         "pay_date": pay_date, "amount": amount})
            i += 5
        else:
            i += 1
    return rows


def check_etf_distributions(etf_positions: dict, state: dict) -> list:
    notifications = []
    session = _kind_session()
    try:
        filings = search_kind_distribution_filings(session, DIVIDEND_CONFIG["kind_lookback_days"])
    except Exception as e:
        print(f"  ⚠ KIND ETF 분배금 공시 목록 조회 실패: {e}")
        return notifications

    for filing in filings:
        acptno = filing["acptno"]
        if acptno in state["kind_seen"]:
            continue
        try:
            doc_url = resolve_kind_doc_url(session, acptno)
            doc_resp = session.get(doc_url, timeout=15)
            # 이 문서들은 Content-Type에 charset이 없어 requests가 인코딩을 잘못 추측하는 경우가 있음
            # (실제로는 항상 UTF-8) → resp.text 대신 raw bytes를 직접 UTF-8로 디코딩한다.
            table_rows = parse_kind_distribution_table(doc_resp.content.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"  ⚠ KIND 분배금 문서 파싱 실패 (acptno={acptno}): {e}")
            continue

        matched_any = False
        for row in table_rows:
            if row["name"] not in etf_positions or row["amount"] is None:
                continue
            matched_any = True
            amounts = calc_amounts(row["amount"], etf_positions[row["name"]])
            notifications.append({
                "name": row["name"],
                "per_share": row["amount"],
                "record_date": row["record_date"],
                "pay_date": row["pay_date"],
                "amounts": amounts,
            })
        state["kind_seen"].append(acptno)
        if not matched_any:
            # 보유하지 않은 ETF들만 포함된 일괄공시였을 뿐이므로 정상 - 조용히 넘어감
            pass

    return notifications


# ───────────────────────── 메시지 포맷 & 실행 ─────────────────────────

# my_holdings_report.py가 "💼 실제 보유자산 리포트"로 시작하는 것과 한눈에 구별되도록
# 완전히 다른 이모지+제목을 맨 앞줄에 둔다. 같은 카카오 앱(나에게 보내기)으로 보내는 두 봇의
# 메시지가 카톡 채팅방에서 섞여도, 첫 줄만 보고 바로 구분할 수 있어야 한다.
DIGEST_HEADER = "💰 배당·분배금 공시 알림"


def format_notification(n: dict) -> str:
    lines = [f"· {n['name']} 1주당 {n['per_share']:,}원"]
    if n.get("record_date") or n.get("pay_date"):
        lines.append(f"  기준일 {n.get('record_date', '-')} / 지급일 {n.get('pay_date', '-')}")
    total_pretax = sum(a["pretax"] for a in n["amounts"])
    total_posttax = sum(a["posttax"] for a in n["amounts"])
    for a in n["amounts"]:
        tag = "(과세이연)" if a["deferred"] else ""
        lines.append(f"  {a['account']} {a['qty']}주: {a['pretax']:,}원{tag}")
    lines.append(f"  합계 세전 {total_pretax:,}원 / 세후 {total_posttax:,}원")
    return "\n".join(lines)


def format_digest(notifications: list) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    blocks = [format_notification(n) for n in notifications]
    grand_pretax = sum(a["pretax"] for n in notifications for a in n["amounts"])
    grand_posttax = sum(a["posttax"] for n in notifications for a in n["amounts"])
    lines = [f"{DIGEST_HEADER} ({today})", ""]
    lines.append("\n\n".join(blocks))
    lines.append("")
    lines.append(f"오늘 합계 세전 {grand_pretax:,}원 / 세후 {grand_posttax:,}원 ({len(notifications)}건)")
    return "\n".join(lines)


def main():
    test_mode = "--test" in sys.argv

    if not DIVIDEND_CONFIG["enabled"]:
        raise SystemExit("local_secrets.py에 DART_API_KEY가 없습니다.")

    state = load_state()
    stock_positions, etf_positions = build_holdings_index()

    print(f"국내 개별주식 {len(stock_positions)}종목, ETF {len(etf_positions)}종목 확인 중...")
    dart_notifications = check_dart_dividends(stock_positions, state)
    etf_notifications = check_etf_distributions(etf_positions, state)
    all_notifications = dart_notifications + etf_notifications

    if not all_notifications:
        print("새로운 배당/분배금 공시 없음.")
        if not test_mode:
            save_state(state)
        return

    digest = format_digest(all_notifications)
    print(digest)
    if not test_mode:
        send_kakao_message(digest)
        save_state(state)
        print(f"\n총 {len(all_notifications)}건 카카오톡 발송 완료.")
    else:
        print(f"\n[--test 모드] 총 {len(all_notifications)}건 발견 (발송/상태저장 안 함).")


if __name__ == "__main__":
    main()
