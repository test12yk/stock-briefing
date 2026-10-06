# -*- coding: utf-8 -*-
"""
dividend_bot.py 전용 카카오톡 "나에게 보내기" 발송 모듈.

kakao_notify.py와 로직은 동일하지만, my_holdings_report.py와는 다른 카카오 앱
(DIVIDEND_KAKAO_CONFIG, dividend_kakao_token.json)을 사용한다 - 카카오톡 메시지에 뜨는
"APP OOO" 발신 앱 라벨을 서로 다르게 보이게 하기 위해 의도적으로 분리했다
(kakao_notify.py/kakao_setup.py가 stock-bot/stock-briefing 사이에서도 이미 같은
이유로 저장소별로 복제되어 있는 것과 같은 패턴).

사전 준비 (최초 1회): README.md의 "배당봇 전용 카카오 앱 설정" 참고.
"""
import json
import os
import requests

from config import DIVIDEND_KAKAO_CONFIG

TOKEN_FILE = "dividend_kakao_token.json"


def _load_tokens():
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "배당봇용 카카오 인증 토큰이 없습니다. 먼저 `python3 dividend_kakao_setup.py`를 실행해서 "
            "최초 1회 인증을 완료하세요."
        )
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tokens(tokens: dict):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def _refresh_access_token(refresh_token: str) -> dict:
    token_data = {
        "grant_type": "refresh_token",
        "client_id": DIVIDEND_KAKAO_CONFIG["rest_api_key"],
        "refresh_token": refresh_token,
    }
    if DIVIDEND_KAKAO_CONFIG.get("client_secret"):
        token_data["client_secret"] = DIVIDEND_KAKAO_CONFIG["client_secret"]

    resp = requests.post("https://kauth.kakao.com/oauth/token", data=token_data, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    tokens = _load_tokens()
    tokens["access_token"] = result["access_token"]
    if "refresh_token" in result:
        tokens["refresh_token"] = result["refresh_token"]
    _save_tokens(tokens)
    return tokens


KAKAO_TEXT_LIMIT = 180


def _split_message(text: str, limit: int = KAKAO_TEXT_LIMIT) -> list:
    chunks = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current = line
    if current:
        chunks.append(current)
    return chunks


def _send_single(text: str) -> bool:
    tokens = _load_tokens()
    template = {
        "object_type": "text",
        "text": text[:KAKAO_TEXT_LIMIT],
        "link": {"web_url": "https://finance.naver.com", "mobile_web_url": "https://finance.naver.com"},
    }

    def _do_send(access_token: str):
        return requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {access_token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=10,
        )

    resp = _do_send(tokens["access_token"])
    if resp.status_code == 401:
        tokens = _refresh_access_token(tokens["refresh_token"])
        resp = _do_send(tokens["access_token"])

    if resp.status_code == 200:
        return True
    print(f"⚠ 카카오톡 발송 실패 ({resp.status_code}): {resp.text}")
    return False


def send_kakao_message(text: str) -> bool:
    """카카오톡 '나에게 보내기'로 메시지를 전송한다. 200자 초과 시 여러 건으로 나눠 보낸다."""
    chunks = _split_message(text)
    all_ok = True
    for chunk in chunks:
        if not _send_single(chunk):
            all_ok = False
    return all_ok
