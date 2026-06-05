"""기술적 지표 및 ML 피처 생성.

주가 예측의 핵심은 '내일을 맞추는 마법'이 아니라,
과거 가격/거래량에서 의미 있는 신호(피처)를 뽑아내는 것이다.
여기서는 교과서적인 기술적 지표들을 피처로 만든다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import data as _data  # 거시지표 병합용


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI(상대강도지수): 최근 상승폭 대비 하락폭. 70↑ 과매수, 30↓ 과매도."""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV로부터 피처 테이블을 만든다. 마지막 행은 '예측 대상(미래)'이라 타깃이 NaN."""
    out = pd.DataFrame(index=df.index)
    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)

    # 수익률 (다양한 기간)
    out["ret_1"] = close.pct_change(1)
    out["ret_5"] = close.pct_change(5)
    out["ret_10"] = close.pct_change(10)

    # 이동평균 대비 현재가 (추세)
    out["ma5_ratio"] = close / close.rolling(5).mean() - 1
    out["ma20_ratio"] = close / close.rolling(20).mean() - 1
    out["ma60_ratio"] = close / close.rolling(60).mean() - 1

    # 변동성
    out["vol_10"] = close.pct_change().rolling(10).std()
    out["vol_20"] = close.pct_change().rolling(20).std()

    # 거래량 변화
    out["vol_ratio"] = volume / volume.rolling(20).mean() - 1

    # RSI
    out["rsi_14"] = rsi(close, 14)

    # 고가/저가 위치 (오늘 종가가 최근 범위 어디쯤?)
    high_20 = df["High"].rolling(20).max()
    low_20 = df["Low"].rolling(20).min()
    out["pos_20"] = (close - low_20) / (high_20 - low_20).replace(0, np.nan)

    # 52주(약 252거래일) 범위 내 위치 — 1에 가까우면 신고가권, 0이면 신저가권
    high_252 = df["High"].rolling(252, min_periods=60).max()
    low_252 = df["Low"].rolling(252, min_periods=60).min()
    out["pos_252"] = (close - low_252) / (high_252 - low_252).replace(0, np.nan)
    out["pos_252"] = out["pos_252"].clip(0, 1)

    # 120일(약 6개월) 장기 추세
    out["ma120_ratio"] = close / close.rolling(120, min_periods=60).mean() - 1

    # MACD(12,26,9) — 추세 전환·모멘텀. 히스토그램 부호 변화로 골든/데드크로스 감지
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    hist = macd - macd_sig
    out["macd_hist_norm"] = hist / close.replace(0, np.nan)  # ML 피처(가격 정규화)
    out["macd_gc"] = ((hist > 0) & (hist.shift(1) <= 0)).astype(float)  # 상승 전환(골든크로스)
    out["macd_dc"] = ((hist < 0) & (hist.shift(1) >= 0)).astype(float)  # 하락 전환(데드크로스)

    # 지지/저항 — 직전 60일(약 3개월) 고점 돌파 / 저점 이탈 (당일 제외)
    hi60 = df["High"].rolling(60, min_periods=20).max().shift(1)
    lo60 = df["Low"].rolling(60, min_periods=20).min().shift(1)
    out["breakout_up"] = (close > hi60).astype(float)
    out["breakdown"] = (close < lo60).astype(float)

    # 거시지표(시장 상황): 코스피·나스닥·환율의 20일 변화 — 날짜로 병합, 없으면 0
    try:
        macro = _data.get_macro()
    except Exception:
        macro = pd.DataFrame()
    for col in MACRO_COLUMNS:
        if len(macro) and col in macro.columns:
            out[col] = macro[col].reindex(out.index, method="ffill")
        else:
            out[col] = 0.0
    out[MACRO_COLUMNS] = out[MACRO_COLUMNS].fillna(0.0)

    return out


MACRO_COLUMNS = ["mac_kospi20", "mac_nasdaq20", "mac_fx20"]

TECH_COLUMNS = [
    "ret_1", "ret_5", "ret_10",
    "ma5_ratio", "ma20_ratio", "ma60_ratio", "ma120_ratio",
    "vol_10", "vol_20", "vol_ratio", "rsi_14", "pos_20", "pos_252",
    "macd_hist_norm",
]
FEATURE_COLUMNS = TECH_COLUMNS + MACRO_COLUMNS


def make_dataset(df: pd.DataFrame):
    """피처 X와 타깃 y(다음날 상승=1, 하락=0)를 만든다.

    반환: (X, y, feat_full)
      - X, y: 학습용 (타깃이 정의된 구간)
      - feat_full: 마지막 행 포함 전체 피처 (미래 예측용)
    """
    feat = build_features(df)
    close = df["Close"].astype(float)
    # 타깃: 다음날 종가가 오늘보다 높으면 1
    future_up = (close.shift(-1) > close).astype(float)
    feat["target"] = future_up

    full = feat.dropna(subset=FEATURE_COLUMNS)
    train = full.dropna(subset=["target"])  # 마지막 행(타깃 NaN) 제외

    X = train[FEATURE_COLUMNS]
    y = train["target"].astype(int)
    return X, y, full
