# -*- coding: utf-8 -*-
"""
보유/관심 종목 관련 최신 뉴스 헤드라인을 가져온다.
구글 뉴스 RSS를 사용하므로 별도 API 키가 필요 없다.
"""
import xml.etree.ElementTree as ET

import requests


def fetch_news_headlines(query: str, limit: int = 2) -> list:
    """query(종목명/티커)로 구글 뉴스를 검색해 최신 헤드라인 리스트를 반환."""
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall("./channel/item")[:limit]
        return [item.findtext("title", "").strip() for item in items]
    except Exception as e:
        print(f"  ⚠ 뉴스 조회 실패 ({query}): {e}")
        return []
