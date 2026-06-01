"""기술적 지표 및 ML 피처 생성.

주가 예측의 핵심은 '내일을 맞추는 마법'이 아니라,
과거 가격/거래량에서 의미 있는 신호(피처)를 뽑아내는 것이다.
여기서는 교과서적인 기술적 지표들을 피처로 만든다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


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

    return out


FEATURE_COLUMNS = [
    "ret_1", "ret_5", "ret_10",
    "ma5_ratio", "ma20_ratio", "ma60_ratio",
    "vol_10", "vol_20", "vol_ratio", "rsi_14", "pos_20",
]


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
