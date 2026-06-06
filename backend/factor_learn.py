"""근거 가중치 학습 — 로지스틱 회귀가 데이터에서 각 근거의 가중치(계수)를 직접 정한다.

①(factor_backtest)이 '근거 하나씩'을 봤다면, 여기선 '여러 근거를 동시에' 넣어
서로의 영향을 보정한 **다변량 가중치**를 학습한다. 표준화(z-score) 후 학습하므로
계수의 크기 = 상대적 중요도, 부호 = 매수(+)/매도(-) 방향.

정직성:
- 종목별로 시간순 앞 70%로 학습, 뒤 30%로 검증 (미래 정보 누설 없음).
- 검증 정확도/AUC가 베이스라인을 넘는지로 '학습된 가중치가 쓸모 있나' 판단.

한계: 기술적·거시 근거만(재무·수급·뉴스는 과거 데이터 없음).

실행: python factor_learn.py [--n 25] [--horizon 5]
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import data  # noqa: E402
from factor_backtest import _universe  # noqa: E402
from features import build_features  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

# 학습에 쓸 근거(피처)와 사람이 정한 '현재 방향'(+면 클수록 매수)
FEATURES = {
    "ma20_ratio": ("20일선 위치(추세)", +1),
    "ma60_ratio": ("60일선 위치(추세)", +1),
    "ma120_ratio": ("120일선 위치(장기추세)", +1),
    "rsi_14": ("RSI", -1),
    "ret_5": ("5일 모멘텀", +1),
    "ret_10": ("10일 모멘텀", +1),
    "ret_20": ("20일 모멘텀", +1),
    "vol_ratio": ("거래량", +1),
    "vol_20": ("변동성", -1),
    "pos_20": ("20일 내 위치", +1),
    "pos_252": ("52주 내 위치(신고가권)", +1),
    "macd_hist_norm": ("MACD 히스토그램", +1),
    "macd_gc": ("MACD 골든크로스", +1),
    "macd_dc": ("MACD 데드크로스", -1),
    "breakout_up": ("3개월 고점 돌파", +1),
    "breakdown": ("3개월 저점 이탈", -1),
    "mac_kospi20": ("코스피 20일 추세", +1),
    "mac_nasdaq20": ("나스닥 20일 추세", +1),
    "mac_fx20": ("환율 20일 변화", 0),
}


def run(n: int, horizon: int):
    cols = list(FEATURES)
    codes = _universe(n)
    print(f"분석 종목: {len(codes)}개 | 타깃: {horizon}일 뒤 상승 | 불러오는 중…")

    tr_X, tr_y, te_X, te_y = [], [], [], []
    for i, code in enumerate(codes, 1):
        try:
            df = data.get_ohlcv(code)
            if len(df) < 400:
                continue
            feat = build_features(df)
            close = df["Close"].astype(float)
            feat["y"] = (close.shift(-horizon) > close).astype(float)
            feat = feat[cols + ["y"]].replace([np.inf, -np.inf], np.nan).dropna()
            cut = int(len(feat) * 0.7)  # 시간순 앞 70% 학습 / 뒤 30% 검증
            tr_X.append(feat[cols].iloc[:cut]); tr_y.append(feat["y"].iloc[:cut])
            te_X.append(feat[cols].iloc[cut:]); te_y.append(feat["y"].iloc[cut:])
        except Exception:
            pass
        if i % 10 == 0:
            print(f"  {i}/{len(codes)}")

    Xtr = pd.concat(tr_X); ytr = pd.concat(tr_y).astype(int)
    Xte = pd.concat(te_X); yte = pd.concat(te_y).astype(int)
    print(f"\n학습 표본 {len(Xtr):,} / 검증 표본 {len(Xte):,}\n")

    scaler = StandardScaler().fit(Xtr)
    clf = LogisticRegression(C=1.0, max_iter=1000)
    clf.fit(scaler.transform(Xtr), ytr)

    # 성능 (검증 = 미래 구간)
    p_te = clf.predict_proba(scaler.transform(Xte))[:, 1]
    acc = accuracy_score(yte, (p_te >= 0.5).astype(int))
    auc = roc_auc_score(yte, p_te)
    base = max(yte.mean(), 1 - yte.mean())
    print("=" * 70)
    print("성능 (검증 = 각 종목 뒤 30% 미래 구간)")
    print("=" * 70)
    print(f"  정확도 {acc:.3f}  vs  베이스라인(항상 다수) {base:.3f}   → "
          f"{'✅ 베이스라인 상회' if acc > base + 0.002 else '⚠️ 베이스라인과 비슷'}")
    print(f"  AUC {auc:.3f}  (0.5=무작위, 0.5 초과면 변별력 있음)")

    # 학습된 가중치(계수) — 크기순
    coefs = clf.coef_[0]
    order = np.argsort(-np.abs(coefs))
    scale = 2.0 / (np.max(np.abs(coefs)) or 1)  # 최대를 ±2로 맞춰 현재 점수와 비교
    print("\n" + "=" * 70)
    print("학습된 가중치 — 크기=중요도, 부호=매수(+)/매도(-)")
    print("=" * 70)
    print(f"{'근거':<24}{'학습값':>9}{'점수환산':>9}  {'사람직관':>8}  판정")
    for idx in order:
        col = cols[idx]
        label, direction = FEATURES[col]
        w = coefs[idx]
        scaled = w * scale
        human = "+" if direction > 0 else ("-" if direction < 0 else "0")
        learned_sign = "+" if w > 0 else "-"
        if abs(w) < 0.01:
            verdict = "거의 무의미"
        elif direction == 0:
            verdict = "(중립 항목)"
        elif (w > 0) == (direction > 0):
            verdict = "✅ 직관과 일치"
        else:
            verdict = "⚠️ 직관과 반대"
        print(f"{label:<24}{w:>+9.3f}{scaled:>+9.2f}  {human:>8}  {verdict}")

    print("\n해석:")
    print(" - '점수환산'을 현재 investment_signal의 ±점수 대신 쓰면 데이터 기반 가중치가 됨.")
    print(" - '직관과 반대'인 근거는 사람이 부호를 잘못 준 것(데이터는 다르게 봄).")
    print(" - 검증 정확도가 베이스라인을 넘어야 이 가중치를 신뢰할 수 있음.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--horizon", type=int, default=5)
    args = ap.parse_args()
    run(args.n, args.horizon)
