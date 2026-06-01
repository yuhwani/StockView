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

    return {
        "prediction": {
            "direction": "상승" if proba_up >= 0.5 else "하락",
            "probability_up": round(proba_up, 4),
            "confidence": round(abs(proba_up - 0.5) * 2, 4),  # 0~1
        },
        "evaluation": {
            "accuracy": round(accuracy, 4),
            "baseline": round(baseline, 4),
            "edge": round(accuracy - baseline, 4),  # 베이스라인 대비 우위
            "up_recall": round(up_recall, 4),
            "test_size": int(len(X_test)),
            "train_size": int(len(X_train)),
        },
        "feature_importance": [
            {"feature": f, "importance": round(float(imp), 4)}
            for f, imp in importances
        ],
    }
