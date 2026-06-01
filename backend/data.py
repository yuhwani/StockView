"""주식 데이터 수집 (FinanceDataReader 기반) — 한국 + 미국."""
from __future__ import annotations

import time

import FinanceDataReader as fdr
import pandas as pd
import requests

_LISTING_TTL = 60 * 60 * 6  # 6시간 (시총/등락률은 자주 안 바뀌므로)

# 원본 리스트 캐시: 한 번 받아서 검색·목록 양쪽에 재사용한다.
_raw: dict[str, object] = {"krx": None, "us": None, "sp500": None, "ts": 0.0}


def _load_raw() -> None:
    """KRX(시총 포함) / 미국 거래소 / S&P500 원본 리스트를 한 번에 적재."""
    now = time.time()
    if _raw["krx"] is not None and now - _raw["ts"] <= _LISTING_TTL:
        return

    # 한국: 시총(Marcap), 등락률, 거래대금까지 들어있는 풍부한 리스트
    try:
        _raw["krx"] = fdr.StockListing("KRX")
    except Exception as e:
        print(f"[listing] KRX 실패: {e}")
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

    _raw["ts"] = now


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
