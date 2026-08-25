# -*- coding: utf-8 -*-
"""
최초 설정 마법사.

실행하면 대화형으로:
  1) 카카오 REST API 키를 입력받아 local_secrets.py를 생성하고
  2) 보유 종목(계좌/종목명/티커/수량/매입단가)을 입력받아 my_portfolio.py를 생성합니다.

반드시 실제 터미널(대화형 입력이 되는 환경)에서 실행하세요.
    python3 setup.py

다시 실행하면 기존 파일을 덮어씁니다 (종목을 새로 등록하고 싶을 때 다시 실행하면 됨).
"""
import re


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def setup_kakao():
    print("=" * 60)
    print("1) 카카오톡 '나에게 보내기' 알림 설정 (건너뛰려면 그냥 엔터)")
    print("   - developers.kakao.com 에서 앱을 만들고 REST API 키를 발급받으세요.")
    print("=" * 60)
    key = ask("카카오 REST API 키")
    with open("local_secrets.py", "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        if key:
            f.write(f'KAKAO_REST_API_KEY = "{key}"\n')
        else:
            f.write("KAKAO_REST_API_KEY = None  # 카카오 알림을 쓰지 않음\n")
    if key:
        print("✅ local_secrets.py 생성 완료. 다음으로 `python3 kakao_setup.py`를 실행해서")
        print("   카카오 로그인 인증을 완료하세요 (최초 1회).")
    else:
        print("⚠ 카카오 API 키를 입력하지 않았습니다. 카카오톡 알림 없이 콘솔 출력만 사용됩니다.")


def setup_portfolio():
    print()
    print("=" * 60)
    print("2) 보유 종목 입력")
    print("   야후 파이낸스 티커 형식으로 입력하세요 (한국 종목은 .KS/.KQ 필수, 예: 005930.KS)")
    print("   종목명 입력 없이 엔터만 치면 입력을 종료합니다.")
    print("=" * 60)

    holdings = []
    while True:
        name = input("\n종목명 (엔터=종료): ").strip()
        if not name:
            break
        ticker = ask("  티커 (예: 005930.KS, AAPL)")
        if not ticker:
            print("  ⚠ 티커는 필수입니다. 이 종목은 건너뜁니다.")
            continue
        account = ask("  계좌명", "기본계좌")
        kind = ask("  구분 (주식/ETF)", "주식")
        qty_raw = ask("  보유 수량", "0")
        try:
            qty = float(qty_raw) if "." in qty_raw else int(qty_raw)
        except ValueError:
            print("  ⚠ 숫자가 아니어서 0으로 처리합니다.")
            qty = 0
        avg_raw = ask("  매입단가(원, 모르면 엔터)")
        avg_price = None
        if avg_raw:
            avg_clean = re.sub(r"[^\d.]", "", avg_raw)
            avg_price = float(avg_clean) if avg_clean else None

        holdings.append({
            "account": account, "name": name, "ticker": ticker,
            "kind": kind, "qty": qty, "avg_price": avg_price,
        })
        print(f"  → 추가됨: {account}/{name}({ticker}) x{qty}")

    with open("my_portfolio.py", "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write('"""setup.py로 생성된 실제 보유 종목 목록. 직접 수정해도 됩니다."""\n\n')
        f.write("MY_HOLDINGS = [\n")
        for h in holdings:
            f.write(f"    {h!r},\n")
        f.write("]\n")

    print(f"\n✅ my_portfolio.py 생성 완료 ({len(holdings)}개 종목).")


def main():
    setup_kakao()
    setup_portfolio()
    print()
    print("=" * 60)
    print("설정 완료! 이제 다음을 실행하세요:")
    print("  1) python3 kakao_setup.py   (카카오 알림 설정했다면, 최초 1회)")
    print("  2) python3 my_holdings_report.py   (리포트 생성 + 발송)")
    print("=" * 60)


if __name__ == "__main__":
    main()
