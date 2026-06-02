"""DART 전자공시 연동 — 종목의 주요 공시(재료)를 실시간 감지.

뉴스 키워드 추정 대신 **실제 공시 보고서명**으로 자사주취득·신규시설투자·
대형 공급계약 등을 정확히 잡는다. 한국 종목만 해당.

DART_API_KEY(.env)가 없으면 조용히 빈 결과를 반환한다.
"""
from __future__ import annotations

import io
import os
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()
_KEY = (os.environ.get("DART_API_KEY") or "").strip()
_VALID = bool(_KEY) and _KEY != "여기에_키_붙여넣기"

_BASE = "https://opendart.fss.or.kr/api"

# 종목코드 → DART corp_code 매핑 (거의 안 바뀌므로 길게 캐싱)
_corp_map: dict[str, str] | None = None
_corp_ts = 0.0
_CORP_TTL = 60 * 60 * 24  # 24시간

# 공시 결과 캐시 (종목별 1시간)
_disc_cache: dict[str, tuple[float, list]] = {}
_DISC_TTL = 60 * 60

# 공시 보고서명 → 재료(이벤트) 분류
_EVENTS = [
    ("자사주 취득(공시)", ["자기주식취득", "자기주식 취득"], "good"),
    ("신규 시설투자(공시)", ["신규시설투자", "유형자산 양수", "신규 시설"], "good"),
    ("대형 공급계약·수주(공시)", ["단일판매", "공급계약", "수주"], "good"),
    ("무상증자(공시)", ["무상증자"], "good"),
    ("유상증자(공시)", ["유상증자"], "bad"),
    ("악재 공시(횡령·배임·감자 등)",
     ["횡령", "배임", "감자결정", "상장폐지", "거래정지"], "bad"),
]


def is_enabled() -> bool:
    return _VALID


def _load_corp_map() -> dict[str, str]:
    global _corp_map, _corp_ts
    now = time.time()
    if _corp_map is not None and now - _corp_ts <= _CORP_TTL:
        return _corp_map
    m: dict[str, str] = {}
    try:
        r = requests.get(f"{_BASE}/corpCode.xml", params={"crtfc_key": _KEY}, timeout=30)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        root = ET.fromstring(z.read(z.namelist()[0]))
        for item in root.iter("list"):
            sc = (item.findtext("stock_code") or "").strip()
            cc = (item.findtext("corp_code") or "").strip()
            if sc and cc:
                m[sc] = cc
    except Exception as e:
        print(f"[dart] corp_code 매핑 실패: {e}")
    _corp_map = m
    _corp_ts = now
    return m


def get_disclosures(stock_code: str, days: int = 30, limit: int = 15) -> list[dict]:
    """최근 N일 공시 목록 [{date, title}]. 키 없거나 미상장이면 []."""
    if not _VALID or not (stock_code.isdigit() and len(stock_code) == 6):
        return []

    key = f"{stock_code}:{days}"
    now = time.time()
    if key in _disc_cache and now - _disc_cache[key][0] < _DISC_TTL:
        return _disc_cache[key][1]

    out: list[dict] = []
    try:
        corp = _load_corp_map().get(stock_code)
        if corp:
            bgn = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
            r = requests.get(f"{_BASE}/list.json", timeout=12, params={
                "crtfc_key": _KEY, "corp_code": corp,
                "bgn_de": bgn, "page_count": 100,
            })
            d = r.json()
            if d.get("status") == "000":
                for it in d.get("list", [])[:limit]:
                    out.append({
                        "date": it.get("rcept_dt", ""),
                        "title": it.get("report_nm", ""),
                    })
    except Exception as e:
        print(f"[dart] {stock_code} 공시 조회 실패: {e}")

    _disc_cache[key] = (now, out)
    return out


def detect_events(stock_code: str) -> list[dict]:
    """최근 공시에서 재료(이벤트) 분류 태그를 추출 [{label, tone}]."""
    disclosures = get_disclosures(stock_code)
    blob = " ".join(d["title"] for d in disclosures)
    events = []
    for label, keywords, tone in _EVENTS:
        if any(k in blob for k in keywords):
            events.append({"label": label, "tone": tone})
    return events
