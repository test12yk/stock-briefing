# -*- coding: utf-8 -*-
"""
카카오톡 '나에게 보내기' 최초 1회 인증 스크립트.

사전에 config.py의 KAKAO_CONFIG에 rest_api_key / redirect_uri를 채워 넣고 실행하세요.

사용법 1 (대화형 터미널 - 실제 터미널 앱에서):
  python3 kakao_setup.py
  → 안내되는 URL을 브라우저에서 열고, 리다이렉트된 URL을 프롬프트에 붙여넣기

사용법 2 (비대화형 - 대화형 입력이 안 되는 환경에서):
  python3 kakao_setup.py "리다이렉트된 URL 또는 code 값"
"""
import json
import re
import sys
from urllib.parse import urlencode

import requests

from config import KAKAO_CONFIG

TOKEN_FILE = "kakao_token.json"


def main():
    rest_api_key = KAKAO_CONFIG.get("rest_api_key")
    redirect_uri = KAKAO_CONFIG.get("redirect_uri")
    if not rest_api_key or rest_api_key.startswith("여기에"):
        print("❌ config.py의 KAKAO_CONFIG['rest_api_key']를 먼저 채워주세요.")
        return

    params = {
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "talk_message",
    }
    auth_url = "https://kauth.kakao.com/oauth/authorize?" + urlencode(params)

    if len(sys.argv) > 1:
        pasted = sys.argv[1].strip()
    else:
        print("=" * 70)
        print("1) 아래 URL을 브라우저에서 열어 카카오 로그인 후 동의해주세요:\n")
        print(auth_url)
        print("\n2) 로그인 후 이동되는 페이지가 에러 화면이라도 괜찮습니다.")
        print("   주소창의 전체 URL(또는 그 안의 code=... 값)을 복사해서 아래에 붙여넣으세요.")
        print("   (대화형 입력이 안 되는 환경이라면 대신")
        print('   `python3 kakao_setup.py "붙여넣을URL"` 형태로 실행하세요)')
        print("=" * 70)
        try:
            pasted = input("\n리다이렉트된 URL 또는 code 값을 붙여넣으세요: ").strip()
        except EOFError:
            print("\n❌ 이 환경에서는 대화형 입력을 받을 수 없습니다.")
            print(f'   먼저 아래 URL을 브라우저에서 열어 인증한 뒤,')
            print(f'   `python3 kakao_setup.py "리다이렉트된 URL"` 로 다시 실행하세요:\n')
            print(auth_url)
            return

    match = re.search(r"code=([^&]+)", pasted)
    code = match.group(1) if match else pasted  # code만 붙여넣었을 수도 있으니 fallback

    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": rest_api_key,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"\n❌ 토큰 발급 실패 ({resp.status_code}): {resp.text}")
        return

    result = resp.json()
    tokens = {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
    }
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 인증 완료! 토큰이 {TOKEN_FILE}에 저장됐습니다.")
    print("   이제 daily_run.py를 실행하면 자동으로 카카오톡 알림이 발송됩니다.")

    # 바로 테스트 발송
    from kakao_notify import send_kakao_message
    ok = send_kakao_message("🎉 스톡봇 카카오 알림 연동 테스트 메시지입니다!")
    print("📩 테스트 메시지 발송:", "성공" if ok else "실패")


if __name__ == "__main__":
    main()
