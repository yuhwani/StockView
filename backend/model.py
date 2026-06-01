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
from sklearn.ensemble import RandomForestClassifier

from features import FEATURE_COLUMNS, make_dataset


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


def investment_signal(row, proba_up: float, edge: float) -> dict:
    """ML 예측 + 기술적 지표를 종합해 '지금 살까/뺄까' 행동 신호를 만든다.

    여러 신호에 점수를 매겨 합산하는 투명한 방식. 각 근거를 사람이 읽을 수 있게
    함께 돌려준다. row 는 마지막 거래일의 피처(Series).
    """
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

    # 점수 → 행동
    if score >= 2.5:
        action, tone, summary = "매수 우위", "buy", "여러 신호가 매수에 우호적입니다."
    elif score >= 1:
        action, tone, summary = "약한 매수", "buy_weak", "조심스럽게 매수에 무게가 실립니다."
    elif score > -1:
        action, tone, summary = "관망", "hold", "방향이 뚜렷하지 않습니다. 지켜보세요."
    elif score > -2.5:
        action, tone, summary = "약한 매도", "sell_weak", "비중을 줄이는 것을 고려해볼 만합니다."
    else:
        action, tone, summary = "매도 우위", "sell", "여러 신호가 매도(비중 축소)에 무게를 둡니다."

    # 신뢰도: 점수 크기 + 모델의 실제 우위(edge) 반영
    confidence = min(abs(score) / 5.0, 1.0)
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


def train_and_evaluate(df: pd.DataFrame) -> dict:
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
    signal = investment_signal(last_features.iloc[0], proba_up, edge)

    return {
        "prediction": {
            "direction": "상승" if proba_up >= 0.5 else "하락",
            "probability_up": round(proba_up, 4),
            "confidence": round(abs(proba_up - 0.5) * 2, 4),  # 0~1
        },
        "signal": signal,
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
