# -*- coding: utf-8 -*-
"""
DART(전자공시시스템) 공시 조회.

DART Open API는 회사명이 아니라 8자리 고유번호(corp_code)로 조회하므로,
최초 1회 전체 상장사 매핑(corpCode.xml, zip으로 내려옴)을 받아
dart_corp_codes.json에 캐싱해두고 이후엔 그 캐시만 사용한다.

미국 종목(ticker가 .KS/.KQ로 안 끝남)이거나 회사명 매칭에 실패하면
"DART 대상 아님"으로 처리하고 조용히 빈 결과를 반환한다 (에러 아님).
"""
import io
import json
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests

CORP_CODE_CACHE = "dart_corp_codes.json"


def _is_domestic_listed(ticker: str) -> bool:
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _load_corp_code_map(api_key: str) -> dict:
    """{회사명: corp_code} 매핑. 캐시 파일이 있으면 그걸 쓰고, 없으면 DART에서 받아 생성."""
    if os.path.exists(CORP_CODE_CACHE):
        with open(CORP_CODE_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(
        "https://opendart.fss.or.kr/api/corpCode.xml",
        params={"crtfc_key": api_key},
        timeout=30,
    )
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")

    root = ET.fromstring(xml_bytes)
    mapping = {}
    for item in root.findall("./list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        if not stock_code or not corp_name or not corp_code:
            continue  # 비상장사는 제외 (매칭 대상 아님)
        mapping[corp_name] = corp_code

    with open(CORP_CODE_CACHE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False)

    return mapping


def get_dart_filings(name: str, ticker: str, days: int = 7, api_key: str = None) -> dict:
    """최근 N일 내 DART 공시 목록을 반환.

    반환 형식:
      대상 아님    -> {"available": False, "reason": "..."}
      대상이지만 공시 없음 -> {"available": True, "filings": []}
      공시 있음    -> {"available": True, "filings": [{"title":..., "date":..., "report_type":...}, ...]}
    """
    if not api_key:
        return {"available": False, "reason": "DART API 키가 설정되지 않음"}

    if not _is_domestic_listed(ticker):
        return {"available": False, "reason": "DART 대상 아님 (국내 상장 종목이 아님)"}

    try:
        corp_map = _load_corp_code_map(api_key)
    except Exception as e:
        return {"available": False, "reason": f"회사코드 매핑 로드 실패: {e}"}

    corp_code = corp_map.get(name)
    if not corp_code:
        return {"available": False, "reason": "DART 대상 아님 (회사명 매칭 실패)"}

    end_de = datetime.now().strftime("%Y%m%d")
    bgn_de = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    resp = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": 20,
        },
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()

    status = result.get("status")
    if status == "013":  # 조회된 데이터 없음
        return {"available": True, "filings": []}
    if status != "000":
        return {"available": False, "reason": f"DART API 오류 ({status}): {result.get('message')}"}

    filings = [
        {
            "title": item.get("report_nm"),
            "date": item.get("rcept_dt"),
            "report_type": item.get("pblntf_ty"),
        }
        for item in result.get("list", [])
    ]
    return {"available": True, "filings": filings}
