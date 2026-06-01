"""펀더멘털·수급 데이터 수집 (무료 소스).

- 한국: 네이버 모바일 증권 통합 API → PER/PBR/배당/외국인비율 + 외국인·기관 순매수(수급)
- 미국: stockanalysis.com overview → PER/목표주가/애널리스트 의견

모두 무료·키 불필요. 종목당 1시간 캐싱.
"""
from __future__ import annotations

import re
import time

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
_TTL = 60 * 60  # 1시간
_cache: dict[str, tuple[float, dict]] = {}


def _num(s) -> float | None:
    """'28.23배', '48.29%', '-1,061,741', '$310.00' → float."""
    if s is None:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s).replace(",", ""))
    return float(m.group()) if m else None


# ── 한국: 네이버 ────────────────────────────────────────────
def _kr(code: str) -> dict:
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    d = requests.get(url, headers=_HEADERS, timeout=12).json()

    info = {it["code"]: it.get("value") for it in d.get("totalInfos", [])}
    out = {
        "per": _num(info.get("per")),
        "pbr": _num(info.get("pbr")),
        "eps": _num(info.get("eps")),
        "dividend_yield": _num(info.get("dividendYieldRatio")),
        "foreign_rate": _num(info.get("foreignRate")),
        "week52_high": _num(info.get("highPriceOf52Weeks")),
        "week52_low": _num(info.get("lowPriceOf52Weeks")),
        "analyst_target": None,
        "analyst_rating": None,
        "supply": None,
    }

    # 수급: 최근 5거래일 외국인·기관 순매수 합 (주식수)
    trend = d.get("dealTrendInfos", [])[:5]
    if trend:
        f_net = sum(_num(t.get("foreignerPureBuyQuant")) or 0 for t in trend)
        o_net = sum(_num(t.get("organPureBuyQuant")) or 0 for t in trend)
        out["supply"] = {
            "foreign_net": int(f_net),
            "inst_net": int(o_net),
            "days": len(trend),
        }
    return out


# ── 미국: stockanalysis.com ─────────────────────────────────
def _us(code: str) -> dict:
    url = f"https://stockanalysis.com/api/symbol/s/{code}/overview"
    d = requests.get(url, headers=_HEADERS, timeout=12).json().get("data", {})
    return {
        "per": _num(d.get("peRatio")),
        "pbr": None,  # 무료 소스에 PBR 없음
        "eps": _num(d.get("eps")),
        "forward_pe": _num(d.get("forwardPE")),
        "dividend_yield": _num(d.get("dividend")),  # "$1.04 (0.33%)" → 1.04 (참고용)
        "foreign_rate": None,
        "week52_high": None,
        "week52_low": None,
        "analyst_target": _num(d.get("target")),
        "analyst_rating": (d.get("analysts") or None),  # "Buy"/"Hold"/"Sell"
        "beta": _num(d.get("beta")),
        "supply": None,
    }


def get_fundamentals(code: str, region: str, force: bool = False) -> dict:
    """종목 펀더멘털+수급. 실패해도 빈 dict로 안전하게 반환."""
    key = f"{region}:{code}"
    now = time.time()
    if not force and key in _cache and now - _cache[key][0] < _TTL:
        return _cache[key][1]

    try:
        data = _us(code) if region == "US" else _kr(code)
    except Exception as e:
        print(f"[fundamentals] {key} 실패: {e}")
        data = {}

    _cache[key] = (now, data)
    return data
