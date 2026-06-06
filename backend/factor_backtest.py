"""근거 기여도 백테스트 — 각 판단 근거가 '미래 수익'을 실제로 예측했는지 측정.

방법:
- 여러 종목·수년치 가격에서 각 기술적 근거(피처)를 복원하고,
  그 값과 'N일 뒤 수익률'의 순위상관(Spearman IC)을 구한다.
- IC가 양수면 '값이 클수록 더 오름'(예측력 有), 0 근처면 무의미.
- 이진 근거(골든크로스·돌파 등)는 신호 발생 시 평균 수익·승률을 본다.

한계: 재무·수급·뉴스·공시는 과거 시점 데이터가 없어 제외(기술적·가격 근거만).

실행: python factor_backtest.py [--n 30] [--horizons 1,5,20]
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 콘솔 한글/기호 출력
except Exception:
    pass

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import data  # noqa: E402
from features import build_features  # noqa: E402

# 분석할 연속형 근거(피처)와 '현재 점수에서의 방향(+면 클수록 매수 가점)'
CONT_FACTORS = {
    "ma20_ratio": ("20일선 위치(추세)", +1),
    "ma60_ratio": ("60일선 위치(추세)", +1),
    "ma120_ratio": ("120일선 위치(장기추세)", +1),
    "rsi_14": ("RSI(과매수/과매도)", -1),     # 현재: 낮을수록 매수(+)
    "ret_5": ("최근 5일 모멘텀", +1),
    "ret_10": ("최근 10일 모멘텀", +1),
    "ret_20": ("최근 20일 모멘텀/상대강도", +1),
    "vol_ratio": ("거래량(평소 대비)", +1),
    "pos_252": ("52주 내 위치(신고가권)", +1),
    "vol_20": ("변동성", -1),                 # 현재: 높으면 감점
    "macd_hist_norm": ("MACD 히스토그램", +1),
}
# 이진 근거(신호 발생 = 1)와 방향
BIN_FACTORS = {
    "macd_gc": ("MACD 골든크로스(상승전환)", +1),
    "macd_dc": ("MACD 데드크로스(하락전환)", -1),
    "breakout_up": ("3개월 고점 돌파", +1),
    "breakdown": ("3개월 저점 이탈", -1),
}


def _spearman(x: pd.Series, y: pd.Series) -> float | None:
    d = pd.concat([x, y], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < 50:
        return None
    rx, ry = d.iloc[:, 0].rank(), d.iloc[:, 1].rank()
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(rx.corr(ry))


def _universe(n: int) -> list[str]:
    """시총 상위에서 분석 대상 종목코드를 뽑는다(코스피+코스닥 섞어서)."""
    codes = []
    for lid in ("kospi_cap", "kosdaq_cap"):
        try:
            for it in data.get_named_list(lid, n):
                codes.append(it["Code"])
        except Exception as e:
            print(f"[universe] {lid} 실패: {e}")
    # 중복 제거, 너무 많지 않게 제한
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c); out.append(c)
    return out[: n * 2]


def run(n: int, horizons: list[int]):
    codes = _universe(n)
    print(f"분석 종목: {len(codes)}개 | 미래 수익률 기간: {horizons}일\n불러오는 중…")

    # 종목별 피처+미래수익을 모아 풀링
    pooled = []  # list of DataFrame
    for i, code in enumerate(codes, 1):
        try:
            df = data.get_ohlcv(code)
            if len(df) < 300:
                continue
            feat = build_features(df)
            close = df["Close"].astype(float)
            for h in horizons:
                feat[f"fwd_{h}"] = close.shift(-h) / close - 1
            pooled.append(feat)
        except Exception:
            pass
        if i % 10 == 0:
            print(f"  {i}/{len(codes)}")

    if not pooled:
        print("데이터 없음 (KRX/네이버 목록을 못 받았을 수 있음)")
        return
    big = pd.concat(pooled, ignore_index=True)
    print(f"\n총 표본: {len(big):,} 종목-일\n")

    # ── 연속형 근거: IC(순위상관) ──
    print("=" * 72)
    print("① 연속형 근거 — IC(미래수익과 순위상관). |IC|>0.02면 의미 있는 편")
    print("=" * 72)
    print(f"{'근거':<26}{'방향':<5}" + "".join(f"IC{h}d".rjust(9) for h in horizons) + "  판정")
    rows = []
    for col, (label, direction) in CONT_FACTORS.items():
        if col not in big:
            continue
        ics = [_spearman(big[col], big[f"fwd_{h}"]) for h in horizons]
        rows.append((label, direction, ics))
    for label, direction, ics in rows:
        cells = "".join((f"{ic:+.3f}".rjust(9) if ic is not None else "—".rjust(9)) for ic in ics)
        # 판정: 가장 긴 기간 IC의 부호가 '현재 방향'과 맞는지 + 크기
        ref = next((ic for ic in reversed(ics) if ic is not None), None)
        if ref is None:
            verdict = "데이터부족"
        elif abs(ref) < 0.015:
            verdict = "거의 무의미"
        elif (ref > 0) == (direction > 0):
            verdict = "✅ 방향 맞음"
        else:
            verdict = "⚠️ 방향 반대!"
        arrow = "▲클수록매수" if direction > 0 else "▼작을수록매수"
        print(f"{label:<26}{arrow:<5}{cells}  {verdict}")

    # ── 이진 근거: 신호 발생 시 평균 미래수익·승률 ──
    print("\n" + "=" * 72)
    print("② 이진 근거 — 신호 발생 시 평균 미래수익 / 승률(양수 비율)")
    print("=" * 72)
    base = {h: big[f"fwd_{h}"].mean() for h in horizons}
    print("기준선(전체 평균):  " + "  ".join(f"{h}d {base[h]*100:+.2f}%" for h in horizons))
    print("-" * 72)
    for col, (label, direction) in BIN_FACTORS.items():
        if col not in big:
            continue
        fired = big[big[col] > 0]
        if len(fired) < 50:
            print(f"{label:<26} 표본 부족({len(fired)})")
            continue
        parts = []
        for h in horizons:
            r = fired[f"fwd_{h}"]
            parts.append(f"{h}d {r.mean()*100:+.2f}% (승{(r > 0).mean()*100:.0f}%)")
        print(f"{label:<26} n={len(fired):>5} | " + " | ".join(parts))

    print("\n해석: IC가 0 근처거나 '방향 반대'인 근거는 점수를 줄이거나 빼는 게 좋고,")
    print("      IC·평균수익이 뚜렷한 근거는 가중치를 키우는 근거가 됩니다.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="시장별 상위 N종목")
    ap.add_argument("--horizons", type=str, default="1,5,20")
    args = ap.parse_args()
    hs = [int(x) for x in args.horizons.split(",") if x.strip()]
    run(args.n, hs)
