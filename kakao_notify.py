# -*- coding: utf-8 -*-
"""
카카오톡 "나에게 보내기" 알림 발송 모듈.

사전 준비 (최초 1회):
  1) https://developers.kakao.com 에서 앱 생성
  2) [내 애플리케이션] > [앱 키] > REST API 키를 config.py의 KAKAO_CONFIG["rest_api_key"]에 입력
  3) [카카오 로그인] 활성화, [동의항목]에서 "카카오톡 메시지 전송(talk_message)" 설정
  4) [카카오 로그인] > [Redirect URI]에 "https://localhost:3000" 등록
     (config.py KAKAO_CONFIG["redirect_uri"]와 동일해야 함)
  5) python3 kakao_setup.py 실행 → 안내에 따라 최초 인증 (브라우저 로그인 1회 필요)
     → kakao_token.json 파일에 토큰 저장됨

이후에는 send_kakao_message()가 만료된 토큰을 자동 갱신하며 동작합니다.
"""
import json
import os
import requests

from config import KAKAO_CONFIG

TOKEN_FILE = "kakao_token.json"


def _load_tokens():
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "카카오 인증 토큰이 없습니다. 먼저 `python3 kakao_setup.py`를 실행해서 "
            "최초 1회 인증을 완료하세요."
        )
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tokens(tokens: dict):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def _refresh_access_token(refresh_token: str) -> dict:
    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": KAKAO_CONFIG["rest_api_key"],
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    tokens = _load_tokens()
    tokens["access_token"] = result["access_token"]
    # 리프레시 토큰도 갱신되는 경우가 있음 (아니면 기존 값 유지)
    if "refresh_token" in result:
        tokens["refresh_token"] = result["refresh_token"]
    _save_tokens(tokens)
    return tokens


# 카카오 기본 템플릿(object_type=text)의 text 필드는 최대 200자.
# 넘으면 여러 건으로 쪼개서 순서대로 보낸다 (줄바꿈 단위로 자르고, 그래도 길면 강제로 자름).
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
            # 한 줄 자체가 limit보다 길면 강제로 잘라서 나눔
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
        # 액세스 토큰 만료 → 리프레시 후 재시도
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
