"""ML 모델 학습 / 예측 / 백테스트.

중요(솔직한 설명):
- 단기 주가 방향(내일 상승/하락) 예측은 본질적으로 매우 어렵다.
  실제 정확도는 보통 50~55% 사이이고, 이는 동전 던지기보다 '아주 조금' 나은 수준이다.
- 그래서 우리는 항상 '베이스라인(무조건 상승에 베팅)'과 비교해서
  모델이 정말 의미가 있는지 정직하게 보여준다.
- 시계열 데이터이므로 절대 셔플하지 않고, 과거로 학습→미래로 검증한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from features import FEATURE_COLUMNS, build_features, make_dataset


# 다기간 예측 horizon (거래일, 라벨)
_HORIZONS = [
    (1, "하루 뒤"),
    (5, "일주일 뒤"),
    (20, "한달 뒤"),
    (60, "장기 (약 3개월)"),
]


def forecast(df: pd.DataFrame) -> dict:
    """하루·일주일·한달·장기 미래 수익률을 회귀로 예측.

    정직성:
    - 단일 가격으로 단정하지 않고 '예상 등락률 + 가격 범위(밴드)'를 준다.
    - 각 기간 예측이 과거 검증에서 방향을 맞춘 비율(dir_accuracy)을 함께 줘서
      신뢰도를 드러낸다. 기간이 길수록 밴드는 넓고 정확도는 보통 낮다.
    """
    feat = build_features(df)
    close = df["Close"].astype(float)
    feat_valid = feat.dropna(subset=FEATURE_COLUMNS)
    X_all = feat_valid[FEATURE_COLUMNS]
    price_now = float(close.iloc[-1])

    items = []
    for h, label in _HORIZONS:
        target = close.shift(-h) / close - 1  # 미래 h일 수익률
        y = target.loc[X_all.index]
        mask = y.notna()
        Xh, yh = X_all[mask], y[mask]
        if len(Xh) < 200:
            continue

        # 시간순 80/20 분할 (셔플 금지)
        split = int(len(Xh) * 0.8)
        X_tr, X_te = Xh.iloc[:split], Xh.iloc[split:]
        y_tr, y_te = yh.iloc[:split], yh.iloc[split:]

        reg = RandomForestRegressor(
            n_estimators=120, max_depth=6, min_samples_leaf=20,
            random_state=42, n_jobs=-1,
        )
        reg.fit(X_tr, y_tr)
        pred_te = reg.predict(X_te)
        mae = float(mean_absolute_error(y_te, pred_te))
        dir_acc = float((np.sign(pred_te) == np.sign(y_te.values)).mean())
        resid_std = float(np.std(y_te.values - pred_te))

        # 최신 데이터까지 다시 학습 후 '지금' 기준 미래 예측
        reg.fit(Xh, yh)
        exp_ret = float(reg.predict(X_all.iloc[[-1]])[0])

        items.append({
            "label": label,
            "days": h,
            "expected_return": round(exp_ret, 4),
            "pred_price": round(price_now * (1 + exp_ret), 2),
            "low": round(price_now * (1 + exp_ret - resid_std), 2),
            "high": round(price_now * (1 + exp_ret + resid_std), 2),
            "dir_accuracy": round(dir_acc, 3),
            "mae": round(mae, 4),
        })

    return {"price_now": round(price_now, 2), "horizons": items}


def backtest(df: pd.DataFrame) -> dict:
    """ML 방향예측대로 매매했을 때의 수익률을 단순보유와 비교 (out-of-sample).

    방식(정직성):
    - 앞 80%로만 학습하고, 뒤 20% 구간에서 매일 '내일 상승' 예측이면 보유(long),
      아니면 현금(0%) 보유하는 long/flat 전략의 누적 수익률을 계산.
    - 같은 구간 '단순 매수 후 보유(buy & hold)'와 비교.
    - 수수료·세금·슬리피지는 미반영(참고용). 더 엄밀한 walk-forward는 TODO.
    """
    X, y, _ = make_dataset(df)
    if len(X) < 250:
        raise ValueError("백테스트에 필요한 데이터가 부족합니다 (최소 250거래일).")

    split = int(len(X) * 0.8)
    X_tr, X_te, y_tr = X.iloc[:split], X.iloc[split:], y.iloc[:split]

    model = RandomForestClassifier(
        n_estimators=200, max_depth=5, min_samples_leaf=20,
        random_state=42, n_jobs=-1,
    )
    model.fit(X_tr, y_tr)
    pred_up = model.predict_proba(X_te)[:, 1] >= 0.5

    close = df["Close"].astype(float)
    nxt_ret = (close.shift(-1) / close - 1)        # 각 날의 '다음날' 실현 수익률
    test_ret = nxt_ret.loc[X_te.index].fillna(0).values

    strat_daily = np.where(pred_up, test_ret, 0.0)  # 상승 예측일만 보유
    strat_eq = np.cumprod(1 + strat_daily)
    hold_eq = np.cumprod(1 + test_ret)
    dates = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in X_te.index]
    n = len(test_ret)

    long_days = int(pred_up.sum())
    hits = int((test_ret[pred_up] > 0).sum()) if long_days else 0

    def mdd(eq):
        peak = np.maximum.accumulate(eq)
        return float((eq / peak - 1).min())

    step = max(1, n // 120)
    curve = [
        {"date": dates[i],
         "strategy": round(float(strat_eq[i] - 1), 4),
         "hold": round(float(hold_eq[i] - 1), 4)}
        for i in range(0, n, step)
    ]
    if (n - 1) % step != 0:
        curve.append({"date": dates[-1],
                      "strategy": round(float(strat_eq[-1] - 1), 4),
                      "hold": round(float(hold_eq[-1] - 1), 4)})

    return {
        "period_start": dates[0],
        "period_end": dates[-1],
        "days": n,
        "long_days": long_days,
        "hit_rate": round(hits / long_days, 3) if long_days else 0.0,
        "strategy_return": round(float(strat_eq[-1] - 1), 4),
        "buyhold_return": round(float(hold_eq[-1] - 1), 4),
        "strategy_mdd": round(mdd(strat_eq), 4),
        "buyhold_mdd": round(mdd(hold_eq), 4),
        "curve": curve,
    }


def quick_predict(df: pd.DataFrame) -> dict:
    """목록 미리보기용 경량 예측: 평가(백테스트) 없이 방향만 빠르게.

    전체 데이터로 한 번만 학습 → '내일' 방향/확률만 반환.
    """
    X, y, full = make_dataset(df)
    if len(X) < 200:
        raise ValueError("데이터 부족")

    model = RandomForestClassifier(
        n_estimators=120, max_depth=5, min_samples_leaf=20,
        random_state=42, n_jobs=-1,
    )
    model.fit(X, y)
    last_features = full[FEATURE_COLUMNS].iloc[[-1]]
    proba_up = float(model.predict_proba(last_features)[0][1])
    return {
        "direction": "상승" if proba_up >= 0.5 else "하락",
        "probability_up": round(proba_up, 4),
        "confidence": round(abs(proba_up - 0.5) * 2, 4),
    }


def investment_signal(row, proba_up: float, edge: float, extras: dict | None = None) -> dict:
    """ML 예측 + 기술적 지표 + 펀더멘털·수급·뉴스를 종합해 행동 신호를 만든다.

    여러 신호에 점수를 매겨 합산하는 투명한 방식. 각 근거를 사람이 읽을 수 있게
    함께 돌려준다. row 는 마지막 거래일의 피처(Series),
    extras 는 {valuation, supply, sentiment, region} (없으면 가격 기반만).
    """
    extras = extras or {}
    score = 0.0
    reasons = []

    # 1) ML 다음날 상승확률
    if proba_up >= 0.55:
        score += 2; reasons.append(("up", f"ML 모델: 다음날 상승확률 {proba_up:.0%} (강세)"))
    elif proba_up >= 0.52:
        score += 1; reasons.append(("up", f"ML 모델: 상승확률 {proba_up:.0%} (약한 강세)"))
    elif proba_up <= 0.45:
        score -= 2; reasons.append(("down", f"ML 모델: 상승확률 {proba_up:.0%} (약세)"))
    elif proba_up <= 0.48:
        score -= 1; reasons.append(("down", f"ML 모델: 상승확률 {proba_up:.0%} (약한 약세)"))
    else:
        reasons.append(("flat", f"ML 모델: 상승확률 {proba_up:.0%} (중립)"))

    # 2) 추세 (20일·60일 이동평균 대비 위치)
    ma20, ma60 = float(row["ma20_ratio"]), float(row["ma60_ratio"])
    if ma20 > 0 and ma60 > 0:
        score += 1.5; reasons.append(("up", "주가가 20일·60일 이동평균선 위 → 상승추세"))
    elif ma20 < 0 and ma60 < 0:
        score -= 1.5; reasons.append(("down", "주가가 20일·60일 이동평균선 아래 → 하락추세"))
    else:
        reasons.append(("flat", "이동평균선 혼조 → 추세 불명확"))

    # 3) RSI (과매수/과매도)
    rsi = float(row["rsi_14"])
    if rsi <= 30:
        score += 1; reasons.append(("up", f"RSI {rsi:.0f} → 과매도 (반등 가능)"))
    elif rsi >= 70:
        score -= 1; reasons.append(("down", f"RSI {rsi:.0f} → 과매수 (조정 주의)"))
    else:
        reasons.append(("flat", f"RSI {rsi:.0f} → 중립 구간"))

    # 4) 최근 5일 모멘텀
    r5 = float(row["ret_5"])
    if r5 > 0.03:
        score += 0.5; reasons.append(("up", f"최근 5일 +{r5:.1%} 상승 모멘텀"))
    elif r5 < -0.03:
        score -= 0.5; reasons.append(("down", f"최근 5일 {r5:.1%} 하락 모멘텀"))

    val = extras.get("valuation") or {}
    sup = extras.get("supply") or {}
    sen = extras.get("sentiment") or {}

    # 5) 밸류에이션 (PER / PBR)
    per, pbr = val.get("per"), val.get("pbr")
    if per and per > 0:
        if per < 10:
            score += 0.5; reasons.append(("up", f"PER {per:.1f} → 저평가 매력"))
        elif per > 40:
            score -= 0.5; reasons.append(("down", f"PER {per:.1f} → 고평가 부담"))
    if pbr and pbr > 0:
        if pbr < 1:
            score += 0.5; reasons.append(("up", f"PBR {pbr:.2f} → 자산가치 이하"))
        elif pbr > 5:
            score -= 0.3; reasons.append(("down", f"PBR {pbr:.1f} → 고PBR"))

    # 6) 수급 (외국인·기관 순매수, 한국)
    fn, inn = sup.get("foreign_net"), sup.get("inst_net")
    if fn is not None and inn is not None:
        if fn > 0 and inn > 0:
            score += 1; reasons.append(("up", "최근 외국인·기관 동반 순매수 (수급 양호)"))
        elif fn < 0 and inn < 0:
            score -= 1; reasons.append(("down", "최근 외국인·기관 동반 순매도 (수급 약화)"))
        elif fn > 0 or inn > 0:
            who = "외국인" if fn > 0 else "기관"
            score += 0.5; reasons.append(("up", f"최근 {who} 순매수"))

    # 7) 뉴스 감성
    sscore = sen.get("score")
    if sscore is not None and sen.get("total"):
        if sscore >= 0.3:
            score += 1; reasons.append(("up", f"최근 뉴스 긍정 우세 (감성 {sscore:+.2f})"))
        elif sscore >= 0.15:
            score += 0.5; reasons.append(("up", f"뉴스 다소 긍정 (감성 {sscore:+.2f})"))
        elif sscore <= -0.3:
            score -= 1; reasons.append(("down", f"최근 뉴스 부정 우세 (감성 {sscore:+.2f})"))
        elif sscore <= -0.15:
            score -= 0.5; reasons.append(("down", f"뉴스 다소 부정 (감성 {sscore:+.2f})"))

    # 8) 재료(이벤트): 자사주매입·증설·최초기술 등
    good_bonus = 0.0
    for ev in sen.get("events", []):
        if ev["tone"] == "good" and good_bonus < 1.0:
            good_bonus += 0.5; reasons.append(("up", f"재료 감지: {ev['label']}"))
        elif ev["tone"] == "bad":
            score -= 1; reasons.append(("down", f"악재 감지: {ev['label']}"))
    score += good_bonus

    # 9) 애널리스트 의견 (미국)
    rating = (val.get("analyst_rating") or "").lower()
    if "buy" in rating:
        score += 0.5; reasons.append(("up", f"애널리스트 컨센서스: {val['analyst_rating']}"))
    elif "sell" in rating:
        score -= 0.5; reasons.append(("down", f"애널리스트 컨센서스: {val['analyst_rating']}"))

    # 점수 → 행동
    if score >= 3:
        action, tone, summary = "매수 우위", "buy", "여러 신호가 매수에 우호적입니다."
    elif score >= 1:
        action, tone, summary = "약한 매수", "buy_weak", "조심스럽게 매수에 무게가 실립니다."
    elif score > -1:
        action, tone, summary = "관망", "hold", "방향이 뚜렷하지 않습니다. 지켜보세요."
    elif score > -3:
        action, tone, summary = "약한 매도", "sell_weak", "비중을 줄이는 것을 고려해볼 만합니다."
    else:
        action, tone, summary = "매도 우위", "sell", "여러 신호가 매도(비중 축소)에 무게를 둡니다."

    # 신뢰도: 점수 크기 + 모델의 실제 우위(edge) 반영
    confidence = min(abs(score) / 6.0, 1.0)
    caveat = None
    if edge <= 0:
        confidence *= 0.6
        caveat = ("이 종목에선 ML 모델이 과거 백테스트에서 베이스라인을 이기지 못했습니다. "
                  "ML 예측보다 추세·RSI 같은 기술적 지표에 더 무게를 두고 판단하세요.")

    return {
        "action": action,
        "tone": tone,
        "score": round(score, 2),
        "confidence": round(confidence, 2),
        "summary": summary,
        "reasons": [{"dir": d, "text": t} for d, t in reasons],
        "caveat": caveat,
    }


def stop_target(df: pd.DataFrame) -> dict:
    """변동성(ATR) 기반 손절가·목표가 제안.

    ATR = 최근 14일 평균 진폭. 손절 = 현재가 - 1.5×ATR, 목표 = 현재가 + 2×ATR.
    (손익비 약 1.3:1). 참고용 기준선이며 절대적 매매가가 아니다.
    """
    high, low, close = df["High"].astype(float), df["Low"].astype(float), df["Close"].astype(float)
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    price = float(close.iloc[-1])

    return {
        "price": round(price, 2),
        "atr": round(atr, 2),
        "atr_pct": round(atr / price, 4) if price else None,
        "stop_loss": round(price - 1.5 * atr, 2),
        "target": round(price + 2.0 * atr, 2),
        "support": round(float(low.rolling(20).min().iloc[-1]), 2),    # 최근 20일 저점
        "resistance": round(float(high.rolling(20).max().iloc[-1]), 2),  # 최근 20일 고점
        "rr": 1.33,
    }


def train_and_evaluate(df: pd.DataFrame, extras: dict | None = None) -> dict:
    X, y, full = make_dataset(df)

    if len(X) < 200:
        raise ValueError("학습에 필요한 데이터가 부족합니다 (최소 200거래일 필요).")

    # 시간순 분할: 앞 80% 학습, 뒤 20% 검증 (셔플 금지)
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 검증 정확도
    test_pred = model.predict(X_test)
    accuracy = float((test_pred == y_test.values).mean())

    # 베이스라인: 검증구간에서 무조건 '상승'에 베팅했을 때 정확도
    baseline = float((y_test == 1).mean())
    baseline = max(baseline, 1 - baseline)  # 다수 클래스 기준

    # 방향별 성능 (상승을 맞춘 비율 등)
    up_mask = y_test.values == 1
    up_recall = float((test_pred[up_mask] == 1).mean()) if up_mask.any() else 0.0

    # 피처 중요도
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda t: t[1],
        reverse=True,
    )

    # 전체 데이터로 다시 학습 후 '내일' 예측
    model_full = RandomForestClassifier(
        n_estimators=300, max_depth=5, min_samples_leaf=20,
        random_state=42, n_jobs=-1,
    )
    model_full.fit(X, y)

    last_features = full[FEATURE_COLUMNS].iloc[[-1]]
    proba_up = float(model_full.predict_proba(last_features)[0][1])

    edge = accuracy - baseline
    signal = investment_signal(last_features.iloc[0], proba_up, edge, extras)

    return {
        "prediction": {
            "direction": "상승" if proba_up >= 0.5 else "하락",
            "probability_up": round(proba_up, 4),
            "confidence": round(abs(proba_up - 0.5) * 2, 4),  # 0~1
        },
        "signal": signal,
        "levels": stop_target(df),
        "evaluation": {
            "accuracy": round(accuracy, 4),
            "baseline": round(baseline, 4),
            "edge": round(edge, 4),  # 베이스라인 대비 우위
            "up_recall": round(up_recall, 4),
            "test_size": int(len(X_test)),
            "train_size": int(len(X_train)),
        },
        "feature_importance": [
            {"feature": f, "importance": round(float(imp), 4)}
            for f, imp in importances
        ],
    }
