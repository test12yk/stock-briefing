# -*- coding: utf-8 -*-
"""
실제 보유 종목(my_portfolio.py의 MY_HOLDINGS, 여러 계좌 지원) 리포트.

- 티커별 수량을 합산해 전체 평가액을 계산
- avg_price(매입단가)가 있는 포지션은 실제 보유손익(%,금액)을 계산해 수익률 top/bottom 종목을 추림
- avg_price가 없는 포지션은 평가액에만 반영하고 손익 계산에서는 제외
- 수익률 top/bottom 종목에 대해서만 뉴스 헤드라인을 붙여 카카오톡 "나에게 보내기"로 전송

사용법: python3 my_holdings_report.py
크론에 등록하려면 (원하는 저장소 경로로 바꿔서):
예) 50 11 * * 1-5 cd /path/to/stock-briefing && python3 my_holdings_report.py >> holdings_log.txt 2>&1
"""
from collections import defaultdict
from datetime import datetime

import yfinance as yf

from config import MY_HOLDINGS_CONFIG, KAKAO_CONFIG
from news_fetcher import fetch_news_headlines

try:
    from my_portfolio import MY_HOLDINGS
except ImportError:
    raise SystemExit(
        "my_portfolio.py가 없습니다. my_portfolio.example.py를 my_portfolio.py로 복사한 뒤 "
        "실제 보유 종목으로 채워 넣으세요: cp my_portfolio.example.py my_portfolio.py"
    )


def fetch_price(ticker: str):
    """현재가를 반환. 실패하면 None."""
    try:
        df = yf.Ticker(ticker).history(period="5d")
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception as e:
        print(f"  ⚠ 시세 조회 실패 ({ticker}): {e}")
        return None


def build_report():
    # 1) 티커별 수량 합산 → 전체 평가액 계산용
    qty_by_ticker = defaultdict(float)
    name_by_ticker = {}
    for h in MY_HOLDINGS:
        qty_by_ticker[h["ticker"]] += h["qty"]
        name_by_ticker[h["ticker"]] = h["name"]

    prices = {}
    for ticker in qty_by_ticker:
        price = fetch_price(ticker)
        if price is not None:
            prices[ticker] = price

    total_value = sum(qty_by_ticker[t] * prices[t] for t in prices)
    failed = sorted({name_by_ticker[t] for t in qty_by_ticker if t not in prices})

    # 2) 매입단가가 있는 포지션(entry 단위)만 실제 손익 계산
    costed_positions = []
    for h in MY_HOLDINGS:
        avg_price = h.get("avg_price")
        price = prices.get(h["ticker"])
        if avg_price and price is not None:
            pnl_pct = (price - avg_price) / avg_price * 100
            pnl_amount = h["qty"] * (price - avg_price)
            costed_positions.append({
                "name": h["name"], "account": h["account"],
                "pnl_pct": pnl_pct, "pnl_amount": pnl_amount,
                "invested": h["qty"] * avg_price, "current": h["qty"] * price,
            })

    total_invested = sum(p["invested"] for p in costed_positions)
    total_current = sum(p["current"] for p in costed_positions)
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

    no_cost = sorted({h["name"] for h in MY_HOLDINGS if not h.get("avg_price")})

    ranked = sorted(costed_positions, key=lambda p: p["pnl_pct"], reverse=True)
    top_n = MY_HOLDINGS_CONFIG.get("top_movers_count", 3)
    gainers = ranked[:top_n]
    losers = sorted(costed_positions, key=lambda p: p["pnl_pct"])[:top_n]

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"💼 실제 보유자산 리포트 ({today})",
        f"총평가액: {total_value:,.0f}원",
        f"손익확인 {len(costed_positions)}종목 기준 - 매입 {total_invested:,.0f} → 평가 {total_current:,.0f} "
        f"({total_pnl:+,.0f}원, {total_pnl_pct:+.1f}%)",
    ]

    if gainers:
        lines.append("\n🏆 수익률 top:")
        for p in gainers:
            lines.append(f"  {p['name']} {p['pnl_pct']:+.1f}% ({p['pnl_amount']:+,.0f}원)")
    if losers:
        lines.append("\n💧 수익률 bottom:")
        for p in losers:
            lines.append(f"  {p['name']} {p['pnl_pct']:+.1f}% ({p['pnl_amount']:+,.0f}원)")

    if failed:
        lines.append(f"\n⚠ 시세 조회 실패: {', '.join(failed)}")
    if no_cost:
        lines.append(f"⚠ 매입단가 미확인(평가액엔 포함, 손익계산 제외): {', '.join(no_cost)}")

    # 수익률 top/bottom 종목만 뉴스 첨부 (너무 길어지지 않도록)
    movers = {p["name"] for p in gainers + losers}
    news_n = MY_HOLDINGS_CONFIG.get("news_for_movers", 1)
    if movers:
        news_lines = []
        for name in movers:
            headlines = fetch_news_headlines(name, news_n)
            for h in headlines:
                news_lines.append(f"  · [{name}] {h}")
        if news_lines:
            lines.append("\n📰 뉴스:")
            lines.extend(news_lines)

    return "\n".join(lines), total_value


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 실제 보유종목 리포트 생성 시작")
    message, total_value = build_report()
    print(message)
    print(f"\n총평가액: {total_value:,.0f}원")

    if KAKAO_CONFIG.get("enabled"):
        try:
            from kakao_notify import send_kakao_message
            ok = send_kakao_message(message)
            print(f"📩 카카오톡 알림 발송: {'성공' if ok else '실패'}")
        except Exception as e:
            print(f"⚠ 카카오톡 알림 발송 중 오류: {e}")


if __name__ == "__main__":
    main()
