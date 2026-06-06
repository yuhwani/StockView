"""주식 데이터 수집 (FinanceDataReader 기반) — 한국 + 미국."""
from __future__ import annotations

import time
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd
import requests

_LISTING_TTL = 60 * 60 * 6  # 6시간 (시총/등락률은 자주 안 바뀌므로)

# KRX 서버가 일시적으로 막혀도 목록이 비지 않도록 마지막 정상본을 디스크에 보관
_KRX_CACHE_FILE = Path(__file__).resolve().parent / "krx_listing.pkl"

# 원본 리스트 캐시: 한 번 받아서 검색·목록 양쪽에 재사용한다.
_raw: dict[str, object] = {"krx": None, "us": None, "sp500": None, "ts": 0.0}


def _krx_ok(df) -> bool:
    return df is not None and not df.empty and "Market" in df.columns


def _load_raw() -> None:
    """KRX(시총 포함) / 미국 거래소 / S&P500 원본 리스트를 한 번에 적재."""
    now = time.time()
    # 정상(비어있지 않은) 캐시가 살아있으면 재사용
    if _krx_ok(_raw["krx"]) and now - _raw["ts"] <= _LISTING_TTL:
        return

    # 한국: 시총(Marcap), 등락률, 거래대금까지 들어있는 풍부한 리스트
    try:
        df = fdr.StockListing("KRX")
        if not _krx_ok(df):
            raise ValueError("KRX 응답이 비었거나 형식이 다름 (서버 일시 차단 가능)")
        _raw["krx"] = df
        try:
            df.to_pickle(_KRX_CACHE_FILE)  # 마지막 정상본 보관
        except Exception:
            pass
    except Exception as e:
        print(f"[listing] KRX 실패: {e}")
        # 1) 메모리에 이전 정상본이 있으면 그대로 유지 (빈 값으로 덮지 않음)
        if _krx_ok(_raw["krx"]):
            print("[listing] 이전 KRX 캐시 유지")
        # 2) 디스크에 저장된 마지막 정상본 사용
        elif _KRX_CACHE_FILE.exists():
            try:
                _raw["krx"] = pd.read_pickle(_KRX_CACHE_FILE)
                print("[listing] 디스크 KRX 캐시 사용 (오프라인 폴백)")
            except Exception:
                _raw["krx"] = pd.DataFrame()
        else:
            _raw["krx"] = pd.DataFrame()

    # 미국: 검색용 (시총 없음)
    us_frames = []
    for key in ("NASDAQ", "NYSE"):
        try:
            df = fdr.StockListing(key).copy()
            df["Market"] = key
            us_frames.append(df)
        except Exception as e:
            print(f"[listing] {key} 실패: {e}")
    _raw["us"] = pd.concat(us_frames, ignore_index=True) if us_frames else pd.DataFrame()

    # 미국 S&P500 (목록용)
    try:
        _raw["sp500"] = fdr.StockListing("S&P500")
    except Exception as e:
        print(f"[listing] S&P500 실패: {e}")
        _raw["sp500"] = pd.DataFrame()

    # KRX가 끝내 비었으면(폴백도 없음) TTL 캐시하지 않고 다음 호출 때 다시 시도하도록
    # ts를 과거로 둬 빠르게 재시도(2분 후)한다.
    _raw["ts"] = now if _krx_ok(_raw["krx"]) else now - _LISTING_TTL + 120


def _krx() -> pd.DataFrame:
    _load_raw()
    return _raw["krx"]


# ---------------------------------------------------------------------------
# 미국 시가총액 (NASDAQ 스크리너 API — 정확한 실시간 시총)
# ---------------------------------------------------------------------------
_us_marcap_cache: dict[str, object] = {"df": None, "ts": 0.0}


def _fetch_us_screener(exchange: str) -> pd.DataFrame:
    """NASDAQ 공개 스크리너에서 한 거래소의 전 종목(시총 포함)을 받아온다."""
    url = "https://api.nasdaq.com/api/screener/stocks"
    params = {"tableonly": "true", "download": "true", "exchange": exchange}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US",
    }
    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    rows = r.json()["data"]["rows"]
    df = pd.DataFrame(rows)
    df["exchange"] = exchange.upper()
    return df


def get_us_marcap() -> pd.DataFrame:
    """NASDAQ+NYSE 종목을 시가총액과 함께 반환. 6시간 캐싱.

    반환 컬럼: Code, Name, Market, Marcap, Close, ChangeRatio, Sector
    """
    now = time.time()
    if _us_marcap_cache["df"] is None or now - _us_marcap_cache["ts"] > _LISTING_TTL:
        frames = []
        for ex in ("nasdaq", "nyse"):
            try:
                frames.append(_fetch_us_screener(ex))
            except Exception as e:
                print(f"[us_marcap] {ex} 실패: {e}")
        if not frames:
            _us_marcap_cache["df"] = pd.DataFrame()
            _us_marcap_cache["ts"] = now
            return _us_marcap_cache["df"]

        raw = pd.concat(frames, ignore_index=True)

        def _to_num(s):
            return pd.to_numeric(
                s.astype(str).str.replace(r"[$,%]", "", regex=True).str.strip(),
                errors="coerce",
            )

        close = _to_num(raw["lastsale"])
        volume = _to_num(raw["volume"]) if "volume" in raw else pd.Series(dtype=float)
        df = pd.DataFrame({
            "Code": raw["symbol"].astype(str).str.strip(),
            "Name": raw["name"].astype(str),
            "Market": raw["exchange"],
            "Marcap": _to_num(raw["marketCap"]),
            "Close": close,
            "ChangeRatio": _to_num(raw["pctchange"]),
            "Volume": volume,
            "Amount": volume * close,  # 거래대금(달러) ≈ 거래량 × 가격
            "Sector": raw.get("sector", "").astype(str),
        })
        # 보통주만: 시총 있고, 워런트/유닛 같은 특수기호(.,^) 제외
        df = df[df["Marcap"] > 0]
        df = df[~df["Code"].str.contains(r"[\.\^/]", regex=True, na=False)]
        df = df.dropna(subset=["Code"]).drop_duplicates(subset=["Code"])
        df = df.sort_values("Marcap", ascending=False).reset_index(drop=True)
        _us_marcap_cache["df"] = df
        _us_marcap_cache["ts"] = now
    return _us_marcap_cache["df"]


# ---------------------------------------------------------------------------
# 검색
# ---------------------------------------------------------------------------
_search_cache: dict[str, object] = {"df": None, "ts": 0.0}


def get_listing() -> pd.DataFrame:
    """검색용 통합 리스트 (Code, Name, Market, Region)."""
    now = time.time()
    if _search_cache["df"] is None or now - _search_cache["ts"] > _LISTING_TTL:
        _load_raw()
        frames = []

        krx = _krx()
        if len(krx):
            k = krx[["Code", "Name", "Market"]].copy()
            k["Region"] = "KR"
            frames.append(k)

        us = _raw["us"]
        if len(us):
            u = us.rename(columns={"Symbol": "Code"})[["Code", "Name", "Market"]].copy()
            u["Region"] = "US"
            frames.append(u)

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.dropna(subset=["Code", "Name"])
        combined = combined.drop_duplicates(subset=["Code"]).reset_index(drop=True)
        _search_cache["df"] = combined
        _search_cache["ts"] = now
    return _search_cache["df"]


def search_stocks(query: str, limit: int = 20) -> list[dict]:
    """이름 또는 코드로 종목 검색 (한국+미국)."""
    df = get_listing()
    q = query.strip()
    if not q:
        return []
    name_mask = df["Name"].astype(str).str.contains(q, case=False, na=False)
    code_mask = df["Code"].astype(str).str.contains(q, case=False, na=False)
    hits = df[name_mask | code_mask]

    # 코드가 검색어와 정확히 일치하면 최상단으로 (예: 'AAPL', '005930')
    exact = hits["Code"].astype(str).str.upper() == q.upper()
    hits = pd.concat([hits[exact], hits[~exact]]).head(limit)
    return hits.to_dict(orient="records")


def _meta(code: str) -> dict | None:
    df = get_listing()
    row = df[df["Code"].astype(str) == code]
    if len(row):
        r = row.iloc[0]
        return {"name": str(r["Name"]), "region": str(r.get("Region", "")),
                "market": str(r.get("Market", ""))}
    return None


def get_name(code: str) -> str | None:
    m = _meta(code)
    return m["name"] if m else None


def get_region(code: str) -> str:
    """차트/통화 표시에 쓰는 지역코드. 코드 형식으로 추정 (6자리 숫자=KR)."""
    m = _meta(code)
    if m and m["region"]:
        return m["region"]
    return "KR" if code.isdigit() and len(code) == 6 else "US"


# ---------------------------------------------------------------------------
# 추천 목록 (코스피/코스닥/시총 100위 등)
# ---------------------------------------------------------------------------

# 목록 정의: id → (이름, 설명, 지역)
LISTS = [
    {"id": "krx_cap100", "name": "한국 시총 100위", "region": "KR",
     "desc": "KOSPI·KOSDAQ 통합 시가총액 상위 100"},
    {"id": "kospi_cap", "name": "코스피 시총 상위", "region": "KR",
     "desc": "KOSPI 시가총액 상위 종목"},
    {"id": "kosdaq_cap", "name": "코스닥 시총 상위", "region": "KR",
     "desc": "KOSDAQ 시가총액 상위 종목"},
    {"id": "krx_gainers", "name": "오늘의 상승률 상위", "region": "KR",
     "desc": "시총 5천억 이상 중 당일 상승률 상위"},
    {"id": "krx_amount", "name": "거래대금 상위", "region": "KR",
     "desc": "당일 거래대금(원) 상위 종목"},
    {"id": "us_cap100", "name": "미국 시총 100위", "region": "US",
     "desc": "NASDAQ·NYSE 통합 시가총액 상위 100 (실시간)"},
    {"id": "us_gainers", "name": "미국 상승률 상위", "region": "US",
     "desc": "시총 100억달러 이상 중 당일 상승률 상위"},
    {"id": "us_sp500", "name": "미국 S&P 500", "region": "US",
     "desc": "S&P 500 구성 종목"},
]


def list_catalog() -> list[dict]:
    return LISTS


def _krx_records(df: pd.DataFrame, limit: int) -> list[dict]:
    """KRX 데이터프레임을 목록 응답 형식으로 변환."""
    df = df.head(limit).copy()
    out = []
    for _, r in df.iterrows():
        out.append({
            "Code": str(r["Code"]),
            "Name": str(r["Name"]),
            "Market": str(r.get("Market", "")),
            "Region": "KR",
            "Close": None if pd.isna(r.get("Close")) else int(r["Close"]),
            "ChangeRatio": None if pd.isna(r.get("ChagesRatio")) else float(r["ChagesRatio"]),
            "Marcap": None if pd.isna(r.get("Marcap")) else int(r["Marcap"]),
        })
    return out


def get_named_list(list_id: str, limit: int = 100) -> list[dict]:
    """지정한 목록의 종목들을 반환."""
    _load_raw()
    krx = _krx()

    # KRX(한국거래소) 서버가 막혀 목록을 못 받았으면 크래시 대신 빈 목록 반환
    if list_id in ("krx_cap100", "kospi_cap", "kosdaq_cap", "krx_gainers", "krx_amount"):
        if not _krx_ok(krx):
            return []

    if list_id == "krx_cap100":
        df = krx.sort_values("Marcap", ascending=False)
        return _krx_records(df, min(limit, 100))

    if list_id == "kospi_cap":
        df = krx[krx["Market"] == "KOSPI"].sort_values("Marcap", ascending=False)
        return _krx_records(df, limit)

    if list_id == "kosdaq_cap":
        df = krx[krx["Market"] == "KOSDAQ"].sort_values("Marcap", ascending=False)
        return _krx_records(df, limit)

    if list_id == "krx_gainers":
        liquid = krx[krx["Marcap"] >= 5e11]  # 시총 5천억 이상만 (잡주 노이즈 제거)
        df = liquid.sort_values("ChagesRatio", ascending=False)
        return _krx_records(df, limit)

    if list_id == "krx_amount":
        df = krx.sort_values("Amount", ascending=False)
        return _krx_records(df, limit)

    if list_id == "us_cap100":
        df = get_us_marcap()
        return _us_records(df, min(limit, 100))

    if list_id == "us_gainers":
        df = get_us_marcap()
        liquid = df[df["Marcap"] >= 1e10]  # 시총 100억달러 이상
        df = liquid.sort_values("ChangeRatio", ascending=False)
        return _us_records(df, limit)

    if list_id == "us_sp500":
        sp = _raw["sp500"]
        if not len(sp):
            return []
        sp = sp.rename(columns={"Symbol": "Code"})
        # S&P500에 정확한 시총을 붙여 시총순으로 정렬
        mc = get_us_marcap()[["Code", "Marcap", "Close", "ChangeRatio"]]
        merged = sp.merge(mc, on="Code", how="left")
        merged = merged.sort_values("Marcap", ascending=False, na_position="last")
        out = []
        for _, r in merged.head(limit).iterrows():
            out.append({
                "Code": str(r["Code"]), "Name": str(r["Name"]),
                "Market": "S&P500", "Region": "US",
                "Sector": str(r.get("Sector", "")),
                "Close": None if pd.isna(r.get("Close")) else float(r["Close"]),
                "ChangeRatio": None if pd.isna(r.get("ChangeRatio")) else float(r["ChangeRatio"]),
                "Marcap": None if pd.isna(r.get("Marcap")) else float(r["Marcap"]),
            })
        return out

    raise ValueError(f"알 수 없는 목록: {list_id}")


def _us_records(df: pd.DataFrame, limit: int) -> list[dict]:
    """미국 시총 데이터프레임을 목록 응답 형식으로 변환 (가격=달러)."""
    df = df.head(limit)
    out = []
    for _, r in df.iterrows():
        out.append({
            "Code": str(r["Code"]),
            "Name": str(r["Name"]),
            "Market": str(r.get("Market", "")),
            "Region": "US",
            "Close": None if pd.isna(r.get("Close")) else float(r["Close"]),
            "ChangeRatio": None if pd.isna(r.get("ChangeRatio")) else float(r["ChangeRatio"]),
            "Marcap": None if pd.isna(r.get("Marcap")) else float(r["Marcap"]),
            "Sector": str(r.get("Sector", "")),
        })
    return out


_OHLCV_TTL = 60 * 30  # 30분 (일봉이라 장중에도 이 정도면 충분)
_ohlcv_cache: dict[str, tuple[float, pd.DataFrame]] = {}

# 거시지표 (시장 상황) — 모든 종목 공통, 날짜로 병합해 ML 피처로 사용
_macro_cache: dict[str, object] = {"df": None, "ts": 0.0}
_MACRO_TTL = 60 * 60 * 6  # 6시간


def get_macro() -> pd.DataFrame:
    """거시지표 파생 피처 (코스피·나스닥·환율의 5/20일 변화). 실패 시 빈 DF."""
    now = time.time()
    if _macro_cache["df"] is not None and now - _macro_cache["ts"] <= _MACRO_TTL:
        return _macro_cache["df"]

    series = {}
    for code, name in [("KS11", "kospi"), ("IXIC", "nasdaq"), ("USD/KRW", "fx")]:
        try:
            series[name] = fdr.DataReader(code, "2017-01-01")["Close"]
        except Exception as e:
            print(f"[macro] {code} 실패: {e}")

    if not series:
        out = pd.DataFrame()
    else:
        m = pd.DataFrame(series).sort_index()
        out = pd.DataFrame(index=m.index)
        if "kospi" in m:
            out["mac_kospi20"] = m["kospi"].pct_change(20)
        if "nasdaq" in m:
            out["mac_nasdaq20"] = m["nasdaq"].pct_change(20)
        if "fx" in m:
            out["mac_fx20"] = m["fx"].pct_change(20)

    _macro_cache["df"] = out
    _macro_cache["ts"] = now
    return out


MACRO_COLUMNS = ["mac_kospi20", "mac_nasdaq20", "mac_fx20"]


_regime_cache: dict[str, object] = {"v": None, "ts": 0.0}
_REGIME_TTL = 60 * 60 * 3  # 3시간


def get_market_regime() -> dict:
    """시장 전체 환경: 공포지수(VIX)와 미국채 10년 금리 방향. 실패해도 None으로 안전."""
    now = time.time()
    if _regime_cache["v"] is not None and now - _regime_cache["ts"] <= _REGIME_TTL:
        return _regime_cache["v"]

    out = {"vix": None, "vix_level": None, "rate_10y": None, "rate_trend": None}
    try:
        vix = fdr.DataReader("VIX", "2024-01-01")["Close"].dropna()
        v = float(vix.iloc[-1])
        out["vix"] = round(v, 1)
        out["vix_level"] = "high" if v >= 25 else ("low" if v <= 15 else "normal")
    except Exception as e:
        print(f"[regime] VIX 실패: {e}")
    try:
        s = fdr.DataReader("FRED:DGS10", "2024-01-01").iloc[:, 0].dropna()
        cur = float(s.iloc[-1])
        past = float(s.iloc[-21]) if len(s) > 21 else float(s.iloc[0])
        out["rate_10y"] = round(cur, 2)
        diff = cur - past  # 최근 약 1개월 금리 변화(%p)
        out["rate_trend"] = "up" if diff >= 0.15 else ("down" if diff <= -0.15 else "flat")
    except Exception as e:
        print(f"[regime] 금리 실패: {e}")

    _regime_cache["v"] = out
    _regime_cache["ts"] = now
    return out


def get_ohlcv(code: str, start: str = "2018-01-01", force: bool = False) -> pd.DataFrame:
    """일봉 OHLCV 데이터. 인덱스는 Date. 한국·미국 코드 모두 지원.

    30분 캐싱하며, force=True면 캐시를 무시하고 최신 데이터를 다시 받는다.
    """
    key = f"{code}:{start}"
    now = time.time()
    cached = _ohlcv_cache.get(key)
    if not force and cached and now - cached[0] < _OHLCV_TTL:
        df = cached[1]
    else:
        df = fdr.DataReader(code, start)
        _ohlcv_cache[key] = (now, df)

    if df.empty:
        raise ValueError(f"'{code}' 데이터를 찾을 수 없습니다.")
    return df.copy()
