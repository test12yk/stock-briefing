# -*- coding: utf-8 -*-
"""
보유/관심 종목 관련 최신 뉴스 헤드라인을 가져온다.
구글 뉴스 RSS를 사용하므로 별도 API 키가 필요 없다.
"""
import xml.etree.ElementTree as ET

import requests


def _shorten_url(url: str) -> str:
    """tinyurl.com(키 불필요)로 줄인다. 구글 뉴스 링크는 200자가 넘어서 카카오톡 메시지
    길이 제한(건당 180자)에 걸려 링크가 중간에서 끊길 수 있어 반드시 줄여야 한다.
    실패하면 원본 URL을 그대로 돌려준다(그 경우 카톡에서 끊길 수 있음을 호출부가 감수)."""
    try:
        resp = requests.get("http://tinyurl.com/api-create.php", params={"url": url}, timeout=5)
        resp.raise_for_status()
        short = resp.text.strip()
        if short.startswith("http"):
            return short
    except Exception:
        pass
    return url


def fetch_news_headlines(query: str, limit: int = 2) -> list:
    """query(종목명/티커)로 구글 뉴스를 검색해 최신 헤드라인을 반환.
    반환값: [{'title': '...', 'link': '...'}, ...]. link는 tinyurl로 줄인 구글 뉴스 링크다
    (최종 언론사 URL은 브라우저에서 JS로만 풀려서 서버에서 직접 못 따라감) -
    실제 폰/브라우저에서 탭하면 정상적으로 원문 기사로 이동한다."""
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall("./channel/item")[:limit]
        return [
            {
                "title": item.findtext("title", "").strip(),
                "link": _shorten_url(item.findtext("link", "").strip()),
            }
            for item in items
        ]
    except Exception as e:
        print(f"  ⚠ 뉴스 조회 실패 ({query}): {e}")
        return []
