"""종목 뉴스 수집 (무료 크롤링).

- 한국: 네이버 모바일 증권 뉴스 API (종목코드 기반, 금융 특화)
- 미국: 구글 뉴스 RSS (회사명 검색, 키 불필요)

AI 요약은 하지 않는다. 실제 뉴스 제목/출처/링크만 그대로 보여주므로
'환각'이 없고, 사용자가 원문을 직접 확인할 수 있다.
"""
from __future__ import annotations

import html
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_TTL = 60 * 15  # 15분 캐싱
_cache: dict[str, tuple[float, list]] = {}


def _clean_us_name(name: str) -> str:
    """구글 뉴스 검색어를 위해 회사명에서 잡다한 접미사 제거."""
    for junk in ["Common Stock", "Class A", "Class C", "Class B",
                 "Ordinary Shares", "Inc.", "Inc", "Corporation",
                 "Corp.", "Corp", "Ltd.", "Ltd", ",", "Holdings"]:
        name = name.replace(junk, "")
    return " ".join(name.split()).strip()


def _fetch_naver(code: str, limit: int) -> list[dict]:
    url = f"https://m.stock.naver.com/api/news/stock/{code}"
    r = requests.get(url, headers=_HEADERS,
                     params={"pageSize": limit + 4, "page": 1}, timeout=12)
    r.raise_for_status()
    groups = r.json()

    out = []
    for g in groups:
        for it in g.get("items", []):
            dt = it.get("datetime", "")
            try:
                pretty = datetime.strptime(dt, "%Y%m%d%H%M").strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pretty = dt
            out.append({
                "title": html.unescape(it.get("titleFull") or it.get("title", "")),
                "source": it.get("officeName", ""),
                "datetime": pretty,
                "url": it.get("mobileNewsUrl", ""),
                "image": it.get("imageOriginLink") or None,
            })
            if len(out) >= limit:
                return out
    return out


def _fetch_google(name: str, limit: int) -> list[dict]:
    query = f"{_clean_us_name(name)} stock"
    url = "https://news.google.com/rss/search"
    r = requests.get(url, headers=_HEADERS,
                     params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                     timeout=12)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    out = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title", "")
        # 구글 뉴스 제목은 "기사제목 - 출처" 형식
        source_el = item.find("{*}source")
        source = source_el.text if source_el is not None else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)]
        pub = item.findtext("pubDate", "")
        try:
            pretty = parsedate_to_datetime(pub).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            pretty = pub
        out.append({
            "title": html.unescape(title),
            "source": source,
            "datetime": pretty,
            "url": item.findtext("link", ""),
            "image": None,
        })
    return out


def get_news(code: str, region: str, name: str, limit: int = 10,
             force: bool = False) -> list[dict]:
    """종목 뉴스 목록. 지역에 맞는 소스에서 가져오고 15분 캐싱."""
    key = f"{region}:{code}"
    now = time.time()
    if not force and key in _cache and now - _cache[key][0] < _TTL:
        return _cache[key][1]

    try:
        if region == "US":
            items = _fetch_google(name or code, limit)
        else:
            items = _fetch_naver(code, limit)
    except Exception as e:
        print(f"[news] {key} 실패: {e}")
        items = []

    _cache[key] = (now, items)
    return items
