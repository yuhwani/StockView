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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from xgboost import XGBClassifier

from features import FEATURE_COLUMNS, build_features, make_dataset


def _fit_proba_model(X, y, n_estimators: int = 120):
    """확률 보정(calibration)을 적용한 RandomForest를 학습해 반환.

    raw 확률은 '55%'라 해도 실제 적중률과 어긋날 수 있다. CalibratedClassifierCV로
    '모델 확률 → 실제 빈도' 매핑을 보정해 '상승확률 55%'가 진짜 55%에 가깝게 만든다.
    데이터가 적거나 한쪽 클래스만 있으면 보정 없이 일반 RF로 폴백.
    """
    base = RandomForestClassifier(
        n_estimators=n_estimators, max_depth=5, min_samples_leaf=20,
        random_state=42, n_jobs=-1,
    )
    try:
        if len(X) >= 600 and getattr(y, "nunique", lambda: 2)() > 1:
            method = "isotonic" if len(X) >= 1500 else "sigmoid"
            clf = CalibratedClassifierCV(base, method=method, cv=3)
            clf.fit(X, y)
            return clf
    except Exception as e:
        print(f"[model] 확률 보정 실패, 일반 RF로 대체: {e}")
    base.fit(X, y)
    return base


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
    """walk-forward 백테스트 — ML 예측대로 매매 vs 단순보유.

    방식(정직성):
    - 데이터 앞 60%부터 시작해, 일정 주기(기본 40거래일)마다 **그 시점까지의
      데이터로만 다시 학습**하고 다음 구간을 예측 (미래 정보 누설 없음).
    - 매일 '내일 상승' 예측이면 보유(long), 아니면 현금(0%)인 long/flat 전략.
    - 같은 구간 '단순 매수 후 보유(buy & hold)'와 비교.
    - 수수료·세금·슬리피지 미반영(참고용).
    """
    X, y, _ = make_dataset(df)
    total = len(X)
    if total < 300:
        raise ValueError("백테스트에 필요한 데이터가 부족합니다 (최소 300거래일).")

    start = int(total * 0.6)
    retrain_every = 40

    close = df["Close"].astype(float)
    nxt_ret = (close.shift(-1) / close - 1)

    proba = np.empty(total - start)
    retrains = 0
    t = start
    while t < total:
        end = min(t + retrain_every, total)
        m = RandomForestClassifier(
            n_estimators=120, max_depth=5, min_samples_leaf=20,
            random_state=42, n_jobs=-1,
        )
        m.fit(X.iloc[:t], y.iloc[:t])          # 그 시점까지의 데이터로만 학습
        proba[t - start:end - start] = m.predict_proba(X.iloc[t:end])[:, 1]
        retrains += 1
        t = end

    idx = X.index[start:]
    pred_up = proba >= 0.5
    test_ret = nxt_ret.loc[idx].fillna(0).values

    strat_daily = np.where(pred_up, test_ret, 0.0)  # 상승 예측일만 보유
    strat_eq = np.cumprod(1 + strat_daily)
    hold_eq = np.cumprod(1 + test_ret)
    dates = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in idx]
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
        "retrains": retrains,
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


def quick_signal(df: pd.DataFrame, extras: dict | None = None) -> dict | None:
    """워커/알림용 빠른 종합 신호 (백테스트·모델비교 없이 신호만)."""
    X, y, full = make_dataset(df)
    if len(X) < 200:
        return None
    m = _fit_proba_model(X, y, n_estimators=120)  # 확률 보정 적용
    last = full[FEATURE_COLUMNS].iloc[[-1]]
    proba = float(m.predict_proba(last)[0][1])
    # 신호 근거는 전체 피처(이진 신호 포함) 행을 넘김. 예측은 FEATURE_COLUMNS만 사용.
    return investment_signal(full.iloc[-1], proba, 0.05, extras)  # edge 양수로 패널티 회피


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
        score += 2; reasons.append(("up", f"AI 예측: 내일 오를 가능성을 {proba_up:.0%}로 높게 봄"))
    elif proba_up >= 0.52:
        score += 1; reasons.append(("up", f"AI 예측: 내일 오를 가능성을 {proba_up:.0%}로 약간 높게 봄"))
    elif proba_up <= 0.45:
        score -= 2; reasons.append(("down", f"AI 예측: 내일 오를 가능성을 {proba_up:.0%}로 낮게 봄"))
    elif proba_up <= 0.48:
        score -= 1; reasons.append(("down", f"AI 예측: 내일 오를 가능성을 {proba_up:.0%}로 약간 낮게 봄"))
    else:
        reasons.append(("flat", f"AI 예측: 내일 방향은 반반 (오를 가능성 {proba_up:.0%})"))

    # 2) 추세 (20일·60일 이동평균 대비 위치)
    ma20, ma60 = float(row["ma20_ratio"]), float(row["ma60_ratio"])
    if ma20 > 0 and ma60 > 0:
        score += 1.5; reasons.append(("up", "최근 한두 달 가격이 꾸준히 우상향 (상승 흐름)"))
    elif ma20 < 0 and ma60 < 0:
        score -= 1.5; reasons.append(("down", "최근 한두 달 가격이 계속 우하향 (하락 흐름)"))
    else:
        reasons.append(("flat", "최근 가격 흐름이 오락가락 (방향 불분명)"))

    # 3) RSI (과매수/과매도)
    rsi = float(row["rsi_14"])
    if rsi <= 30:
        score += 1; reasons.append(("up", "단기간 많이 떨어져 바닥권 → 반등이 나올 수 있음"))
    elif rsi >= 70:
        score -= 1; reasons.append(("down", "단기간 많이 올라 과열권 → 잠시 쉬어갈 수 있음"))
    else:
        reasons.append(("flat", "단기 과열·바닥 신호는 없음 (보통 구간)"))

    # 4) 최근 5일 모멘텀
    r5 = float(row["ret_5"])
    if r5 > 0.03:
        score += 0.5; reasons.append(("up", f"최근 5일간 +{r5:.1%} 올라 분위기가 좋음"))
    elif r5 < -0.03:
        score -= 0.5; reasons.append(("down", f"최근 5일간 {r5:.1%} 내려 분위기가 약함"))

    # 4b) 거래량 (평소 대비) — 추세에 거래량이 실렸는지로 신뢰도 보강
    vr = float(row.get("vol_ratio", 0) or 0)
    if vr >= 0.5:  # 20일 평균 대비 +50% 이상
        if r5 > 0 or ma20 > 0:
            score += 0.5
            reasons.append(("up", f"평소보다 거래가 +{vr:.0%} 늘며 오름 → 상승에 힘이 실림"))
        elif r5 < 0 or ma20 < 0:
            score -= 0.5
            reasons.append(("down", f"평소보다 거래가 +{vr:.0%} 늘며 내림 → 파는 힘이 강함"))
        else:
            reasons.append(("flat", f"평소보다 거래가 +{vr:.0%} 급증 → 관심이 몰림"))
    elif vr <= -0.4:
        reasons.append(("flat", "거래가 평소보다 한산함 (관심 저조)"))

    # 4c) 52주 내 위치 — 신고가권(강세 지속) / 신저가권(약세)
    p252 = row.get("pos_252")
    if p252 is not None and not pd.isna(p252):
        p252 = float(p252)
        if p252 >= 0.9:
            score += 0.5
            reasons.append(("up", "최근 1년 중 가장 높은 가격대 → 강한 상승세"))
        elif p252 <= 0.1:
            score -= 0.4
            reasons.append(("down", "최근 1년 중 가장 낮은 가격대 → 약세"))

    # 4d) 변동성 — 과도하면 신뢰도 낮추고 분할매수·손절 강화 환기
    v20 = float(row.get("vol_20", 0) or 0)
    if v20 >= 0.05:
        score -= 0.2
        reasons.append(("down", f"가격이 하루에도 {v20:.1%}씩 크게 출렁임 → 나눠 사고 손절선 정하기"))

    # 4e) 장기(약 6개월) 추세 — 120일선
    ma120 = row.get("ma120_ratio")
    if ma120 is not None and not pd.isna(ma120):
        ma120 = float(ma120)
        if ma120 > 0.02:
            score += 0.5; reasons.append(("up", "6개월 장기 흐름도 우상향 → 큰 추세가 좋음"))
        elif ma120 < -0.02:
            score -= 0.5; reasons.append(("down", "6개월 장기 흐름이 우하향 → 큰 추세가 약함"))

    # 4f) MACD — 추세 전환 신호 (오늘 막 방향이 바뀐 경우)
    if float(row.get("macd_gc", 0) or 0) > 0:
        score += 0.7; reasons.append(("up", "단기 흐름이 상승으로 막 돌아섬 (상승 전환 신호)"))
    elif float(row.get("macd_dc", 0) or 0) > 0:
        score -= 0.7; reasons.append(("down", "단기 흐름이 하락으로 막 돌아섬 (하락 전환 신호)"))

    # 4g) 지지/저항 돌파 — 최근 3개월 고점 돌파 / 저점 이탈
    if float(row.get("breakout_up", 0) or 0) > 0:
        score += 0.7; reasons.append(("up", "최근 3개월 고점을 뚫음 (저항 돌파 → 강한 상승 신호)"))
    elif float(row.get("breakdown", 0) or 0) > 0:
        score -= 0.7; reasons.append(("down", "최근 3개월 저점을 깸 (지지 이탈 → 약세 신호)"))

    val = extras.get("valuation") or {}
    sup = extras.get("supply") or {}
    sen = extras.get("sentiment") or {}

    # 5) 밸류에이션 (PER / PBR)
    per, pbr = val.get("per"), val.get("pbr")
    if per and per > 0:
        if per < 10:
            score += 0.5; reasons.append(("up", f"버는 이익에 비해 주가가 싼 편 (저평가, PER {per:.1f})"))
        elif per > 40:
            score -= 0.5; reasons.append(("down", f"버는 이익에 비해 주가가 비싼 편 (고평가, PER {per:.1f})"))
    if pbr and pbr > 0:
        if pbr < 1:
            score += 0.5; reasons.append(("up", f"회사 순자산보다 주가가 낮음 (저평가, PBR {pbr:.2f})"))
        elif pbr > 5:
            score -= 0.3; reasons.append(("down", f"회사 순자산보다 주가가 꽤 높음 (PBR {pbr:.1f})"))

    # 5b) 재무 건전성 (ROE·영업이익률·부채비율·매출성장) — 기업 체력
    roe = val.get("roe")
    if roe is not None:
        if roe >= 15:
            score += 0.5; reasons.append(("up", f"자기자본 대비 이익률 높음 (ROE {roe:.0f}%) → 돈을 잘 버는 회사"))
        elif roe < 0:
            score -= 0.5; reasons.append(("down", f"자기자본 대비 이익이 마이너스 (ROE {roe:.0f}%) → 적자"))
    opm = val.get("op_margin")
    if opm is not None:
        if opm >= 15:
            score += 0.3; reasons.append(("up", f"영업이익률이 높음 ({opm:.0f}%) → 본업에서 남는 게 많음"))
        elif opm < 0:
            score -= 0.3; reasons.append(("down", f"영업이익률이 마이너스 ({opm:.0f}%) → 본업이 적자"))
    dr = val.get("debt_ratio")
    if dr is not None:
        if dr >= 200:
            score -= 0.4; reasons.append(("down", f"빚이 많음 (부채비율 {dr:.0f}%) → 재무 부담"))
        elif dr <= 80:
            score += 0.2; reasons.append(("up", f"빚이 적음 (부채비율 {dr:.0f}%) → 재무 안정적"))
    rg = val.get("rev_growth")
    if rg is not None:
        if rg >= 15:
            score += 0.4; reasons.append(("up", f"매출이 1년 전보다 +{rg:.0f}% 성장 → 회사가 커지는 중"))
        elif rg <= -10:
            score -= 0.4; reasons.append(("down", f"매출이 1년 전보다 {rg:.0f}% 줄어듦 → 외형 위축"))

    # 6) 수급 (외국인·기관 순매수, 한국)
    fn, inn = sup.get("foreign_net"), sup.get("inst_net")
    if fn is not None and inn is not None:
        if fn > 0 and inn > 0:
            score += 1; reasons.append(("up", "외국인·기관(큰손)이 함께 사들이는 중 → 수급 양호"))
        elif fn < 0 and inn < 0:
            score -= 1; reasons.append(("down", "외국인·기관(큰손)이 함께 파는 중 → 수급 약화"))
        elif fn > 0 or inn > 0:
            who = "외국인" if fn > 0 else "기관"
            score += 0.5; reasons.append(("up", f"최근 {who}(큰손)이 사들이는 중"))

    # 7) 뉴스 감성
    sscore = sen.get("score")
    if sscore is not None and sen.get("total"):
        if sscore >= 0.3:
            score += 1; reasons.append(("up", "최근 뉴스 분위기가 긍정적"))
        elif sscore >= 0.15:
            score += 0.5; reasons.append(("up", "최근 뉴스 분위기가 다소 긍정적"))
        elif sscore <= -0.3:
            score -= 1; reasons.append(("down", "최근 뉴스 분위기가 부정적"))
        elif sscore <= -0.15:
            score -= 0.5; reasons.append(("down", "최근 뉴스 분위기가 다소 부정적"))

    # 8) 재료(이벤트): 뉴스 키워드 기반
    good_bonus = 0.0
    for ev in sen.get("events", []):
        if ev["tone"] == "good" and good_bonus < 1.0:
            good_bonus += 0.5; reasons.append(("up", f"호재 뉴스: {ev['label']}"))
        elif ev["tone"] == "bad":
            score -= 1; reasons.append(("down", f"악재 뉴스: {ev['label']}"))
    score += good_bonus

    # 8b) DART 공시 기반 재료 (실제 공시라 뉴스보다 신뢰도 높음 → 가중치 ↑)
    dart_bonus = 0.0
    for ev in extras.get("dart_events", []):
        if ev["tone"] == "good" and dart_bonus < 1.5:
            dart_bonus += 0.75; reasons.append(("up", f"회사 공식발표(공시) 호재: {ev['label']}"))
        elif ev["tone"] == "bad":
            score -= 1.5; reasons.append(("down", f"회사 공식발표(공시) 악재: {ev['label']}"))
    score += dart_bonus

    # 8c) 언론 노출 빈도 (주목도): 최근 7일 기사가 많고 + 감성이 긍정이면 가점
    recent7d = sen.get("recent7d", 0)
    if recent7d >= 8:
        if (sscore or 0) >= 0:
            score += 0.3
        reasons.append(("flat", f"요즘 뉴스에 자주 등장 (최근 7일 {recent7d}건, 관심 높음)"))

    # 9) 애널리스트 의견 (미국)
    rating = (val.get("analyst_rating") or "").lower()
    if "buy" in rating:
        score += 0.5; reasons.append(("up", "증권사들 의견: 매수 추천"))
    elif "sell" in rating:
        score -= 0.5; reasons.append(("down", "증권사들 의견: 매도/비중축소"))

    # 10) 공매도 비중 (미국) — 하락 베팅이 많으면 주의
    sp = val.get("short_pct")
    if sp is not None:
        if sp >= 10:
            score -= 0.3; reasons.append(("down", f"공매도 비중 높음 (유통주식의 {sp:.0f}%) → 하락 베팅이 많음(주의)"))
        elif sp >= 5:
            reasons.append(("flat", f"공매도 비중이 다소 있음 ({sp:.0f}%)"))

    # 11) 시장 전체 환경 (공포지수·금리) — 종목 불문 시장 분위기
    reg = extras.get("regime") or {}
    if reg.get("vix_level") == "high":
        score -= 0.3; reasons.append(("down", f"시장 전체가 불안 (공포지수 {reg.get('vix')}) → 변동성 장세, 보수적으로"))
    elif reg.get("vix_level") == "low":
        score += 0.1; reasons.append(("up", f"시장이 안정적 (공포지수 {reg.get('vix')}) → 위험 선호에 우호적"))
    if reg.get("rate_trend") == "up":
        score -= 0.2; reasons.append(("down", "시장 금리가 오르는 추세 → 주식 가치 평가에 부담"))
    elif reg.get("rate_trend") == "down":
        score += 0.2; reasons.append(("up", "시장 금리가 내리는 추세 → 주식에 우호적"))

    # 12) 시장 대비 상대강도 — 같은 기간 지수보다 강한지 (업종/섹터 맥락)
    region = extras.get("region")
    ret20 = row.get("ret_20")
    mkt = row.get("mac_nasdaq20") if region == "US" else row.get("mac_kospi20")
    if (ret20 is not None and not pd.isna(ret20)
            and mkt is not None and not pd.isna(mkt) and float(mkt) != 0):
        rel = float(ret20) - float(mkt)
        if rel >= 0.05:
            score += 0.5; reasons.append(("up", f"최근 한 달 시장지수보다 +{rel * 100:.0f}%p 더 오름 → 시장보다 강함"))
        elif rel <= -0.05:
            score -= 0.5; reasons.append(("down", f"최근 한 달 시장지수보다 {rel * 100:.0f}%p 부진 → 시장보다 약함"))

    # 업종/섹터 (미국) — 점수엔 반영 않고 참고 정보로 표시
    sector = val.get("sector")
    if sector:
        reasons.append(("flat", f"업종: {sector}"))

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
        caveat = ("이 종목은 AI 예측의 과거 적중률이 좋지 않았어요. "
                  "AI 예측보다 가격 흐름·과열 여부 같은 기본 지표를 더 믿고 판단하세요.")

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


def _lstm_accuracy(X, y, window: int = 20, epochs: int = 30) -> float | None:
    """시퀀스 LSTM 검증 정확도 (과거 20일 → 다음날 방향). torch 없으면 None."""
    try:
        import torch
        import torch.nn as nn
    except Exception:
        return None
    try:
        Xv = X.values.astype("float32")
        yv = y.values.astype("float32")
        if len(Xv) < window + 150:
            return None
        seqs = np.stack([Xv[i - window:i] for i in range(window, len(Xv))])
        tgt = yv[window:]
        split = int(len(seqs) * 0.8)
        torch.manual_seed(42)
        Xtr = torch.tensor(seqs[:split])
        ytr = torch.tensor(tgt[:split]).unsqueeze(1)
        Xte = torch.tensor(seqs[split:])
        yte = tgt[split:].astype(int)

        class _Net(nn.Module):
            def __init__(self, nf):
                super().__init__()
                self.lstm = nn.LSTM(nf, 24, batch_first=True)
                self.fc = nn.Linear(24, 1)

            def forward(self, x):
                o, _ = self.lstm(x)
                return torch.sigmoid(self.fc(o[:, -1]))

        m = _Net(Xv.shape[1])
        opt = torch.optim.Adam(m.parameters(), lr=0.01)
        lossf = nn.BCELoss()
        m.train()
        for _ in range(epochs):
            opt.zero_grad()
            loss = lossf(m(Xtr), ytr)
            loss.backward()
            opt.step()
        m.eval()
        with torch.no_grad():
            pred = (m(Xte).squeeze().numpy() >= 0.5).astype(int)
        return float((pred == yte).mean())
    except Exception as e:
        print(f"[lstm] 실패: {e}")
        return None


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

    # 모델 비교: 같은 분할에서 XGBoost 정확도도 측정
    try:
        xgb = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
            random_state=42, n_jobs=-1,
        )
        xgb.fit(X_train, y_train)
        xgb_acc = float((xgb.predict(X_test) == y_test.values).mean())
    except Exception as e:
        print(f"[xgboost] 실패: {e}")
        xgb_acc = None

    lstm_acc = _lstm_accuracy(X, y)  # 시퀀스 LSTM (torch, 실패 시 None)

    model_comparison = [
        {"name": "RandomForest", "accuracy": round(accuracy, 4)},
    ]
    if xgb_acc is not None:
        model_comparison.append({"name": "XGBoost", "accuracy": round(xgb_acc, 4)})
    if lstm_acc is not None:
        model_comparison.append({"name": "LSTM", "accuracy": round(lstm_acc, 4)})
    model_comparison.append({"name": "베이스라인", "accuracy": round(baseline, 4)})

    # 피처 중요도
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda t: t[1],
        reverse=True,
    )

    # 전체 데이터로 다시 학습 후 '내일' 예측 (확률 보정 적용)
    model_full = _fit_proba_model(X, y, n_estimators=300)

    last_features = full[FEATURE_COLUMNS].iloc[[-1]]
    proba_up = float(model_full.predict_proba(last_features)[0][1])

    edge = accuracy - baseline
    signal = investment_signal(full.iloc[-1], proba_up, edge, extras)

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
        "model_comparison": model_comparison,
        "feature_importance": [
            {"feature": f, "importance": round(float(imp), 4)}
            for f, imp in importances
        ],
    }
