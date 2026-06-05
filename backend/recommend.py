"""오늘의 추천 배치 — 넓은 종목군을 빠르게 점수화해 순위를 저장한다.

매일(장 마감 후) 자동 실행되어 recommendations.json 을 갱신한다.
API/프론트는 그 결과 파일을 즉시 읽기만 한다.

설계 포인트:
- universe: 잡주(저시총)는 거르되, **거래대금 상위로 넓게** 잡아
  '밑에서 올라오는' 활발한 중소형주까지 포함한다.
- 점수: 종목당 ML 모델을 새로 학습하면 느리므로, 추천 단계에서는
  **가격 기반 기술적 점수**(추세·모멘텀·거래량 급증·신고가 근접)로 빠르게 매긴다.
  (상세 화면에 들어가면 그때 ML+펀더멘털+뉴스 풀 신호가 돈다.)

실행:
  python recommend.py            # 기본 universe 전체
  python recommend.py --limit 20 # 테스트용 소규모
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import FinanceDataReader as fdr  # noqa: E402
import pandas as pd  # noqa: E402

import data  # noqa: E402
import notify  # noqa: E402
from features import rsi  # noqa: E402

OUT = HERE / "recommendations.json"

# 잡주 필터 하한 (이 시총 미만은 제외, 그 위로는 거래대금 상위로 넓게)
KR_MARCAP_FLOOR = 3e10    # 300억 원
US_MARCAP_FLOOR = 3e8     # 3억 달러
# 거래대금 상위 몇 개까지 점수화할지 (넓게 → 올라오는 중소형주 포착)
N_KR = 600
N_US = 500


def build_universe(n_kr: int, n_us: int) -> list[dict]:
    """잡주를 거르고 거래대금(KR)·시총(US) 상위로 넓게 universe 구성."""
    uni = []
    try:
        krx = data._krx()
        k = krx[(krx["Marcap"] >= KR_MARCAP_FLOOR) & (krx["Amount"] > 0)]
        k = k.sort_values("Amount", ascending=False).head(n_kr)  # 거래대금 상위
        for r in k.itertuples():
            uni.append({"code": str(r.Code), "name": str(r.Name),
                        "market": str(r.Market), "region": "KR"})
    except Exception as e:
        print(f"[universe] KR 실패: {e}")
    try:
        us = data.get_us_marcap()
        u = us[us["Marcap"] >= US_MARCAP_FLOOR]
        # 거래대금(거래량×가격) 상위로 넓게 → 활발한 중소형주 포착
        sort_col = "Amount" if "Amount" in u else "Marcap"
        u = u.sort_values(sort_col, ascending=False).head(n_us)
        for r in u.itertuples():
            uni.append({"code": str(r.Code), "name": str(r.Name),
                        "market": str(r.Market), "region": "US"})
    except Exception as e:
        print(f"[universe] US 실패: {e}")
    return uni


def screen(df: pd.DataFrame) -> dict | None:
    """가격 기반 기술적 점수. 높을수록 매수 매력. 근거(reasons)도 함께."""
    if len(df) < 80:
        return None
    close = df["Close"].astype(float)
    vol = df["Volume"].astype(float)
    price = float(close.iloc[-1])
    if price <= 0:
        return None

    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1]
    ret1 = price / close.iloc[-2] - 1       # 전날
    ret5 = price / close.iloc[-6] - 1       # 일주일 전
    ret10 = price / close.iloc[-11] - 1     # 이주일 전
    ret20 = price / close.iloc[-21] - 1     # 한달 전
    ret60 = price / close.iloc[-61] - 1
    r = float(rsi(close, 14).iloc[-1])
    vol_surge = float(vol.iloc[-5:].mean() / (vol.iloc[-60:].mean() or 1))
    hi = float(close.iloc[-252:].max())
    near_high = price / hi if hi else 0

    score = 0.0
    reasons = []

    # 추세 (정배열)
    if price > ma20 > ma60:
        score += 3; reasons.append("정배열 상승추세 (20·60일선 위)")
    elif price > ma60:
        score += 1.5; reasons.append("60일선 위 (중기 상승)")

    # 중기 모멘텀
    if 0 < ret60 <= 0.6:
        score += min(ret60 / 0.6 * 2, 2); reasons.append(f"60일 +{ret60:.0%} 모멘텀")
    if ret20 > 0:
        score += 1

    # 거래량 급증 (관심 유입 = 올라오는 신호)
    if vol_surge >= 2:
        score += 2; reasons.append(f"거래량 급증 (평소의 {vol_surge:.1f}배)")
    elif vol_surge >= 1.3:
        score += 1; reasons.append(f"거래량 증가 ({vol_surge:.1f}배)")

    # 신고가 근접 (돌파)
    if near_high >= 0.97:
        score += 1.5; reasons.append("52주 신고가 근접 (돌파 시도)")
    elif near_high >= 0.85:
        score += 0.5

    # RSI 과열 페널티 (추격매수 위험)
    if r >= 80:
        score -= 1.5; reasons.append(f"RSI {r:.0f} 과열 (추격 주의)")
    elif 50 <= r < 70:
        score += 0.5

    return {
        "score": round(score, 2),
        "price": round(price, 2),
        "ret1": round(ret1, 4),
        "ret5": round(ret5, 4),
        "ret10": round(ret10, 4),
        "ret20": round(ret20, 4),
        "rsi": round(r, 1),
        "reasons": reasons[:4],
    }


def _fmt_price(v, region):
    if v is None:
        return "-"
    return f"${v:,.2f}" if region == "US" else f"{int(round(v)):,}원"


def _fmt_pct(v):
    if v is None:
        return "-"
    return f"{'+' if v >= 0 else ''}{v * 100:.1f}%"


def _ai_oneliner(top):
    """1등 종목에 대한 AI 한 줄 분석 (키 있을 때만, 실패 시 None)."""
    try:
        import ai
        if not ai.is_enabled():
            return None
        import dart
        import fundamentals
        import news as news_mod
        code, region, name = top["code"], top["region"], top["name"]
        fund = fundamentals.get_fundamentals(code, region)
        items = news_mod.get_news(code, region, name)
        ctx = {
            "roe": fund.get("roe"), "op_margin": fund.get("op_margin"),
            "debt_ratio": fund.get("debt_ratio"), "rev_growth": fund.get("rev_growth"),
            "per": fund.get("per"), "pbr": fund.get("pbr"), "sector": fund.get("sector"),
            "disclosures": [d["title"] for d in dart.get_disclosures(code)[:5]] if region == "KR" else [],
        }
        return ai.analyze(name, code, region, [n.get("title", "") for n in items],
                          top.get("ret1", 0) * 100, "추천 1위", top.get("reasons"), context=ctx)
    except Exception as e:
        print(f"[recommend] AI 한 줄 실패: {e}")
        return None


def notify_top(out: dict):
    """오늘의 추천 1등을 텔레그램(또는 콘솔)으로 발송."""
    buys = out.get("buys", [])
    if not buys:
        print("[recommend] 추천이 없어 알림 생략")
        return
    top = buys[0]
    region = top["region"]
    flag = "🇺🇸" if region == "US" else "🇰🇷"
    lines = [f"🏆 오늘의 추천 1등 ({out['date']})", ""]
    lines.append(f"{flag} {top['name']} ({top['code']})")
    lines.append(f"💰 {_fmt_price(top['price'], region)}")
    lines.append(f"📈 전날 {_fmt_pct(top.get('ret1'))} · 1주 {_fmt_pct(top.get('ret5'))} "
                 f"· 한달 {_fmt_pct(top.get('ret20'))}")
    if top.get("reasons"):
        lines.append("")
        lines.append("📊 선정 이유")
        for r in top["reasons"]:
            lines.append(f"   • {r}")
    ai_text = _ai_oneliner(top)
    if ai_text:
        lines.append("")
        lines.append("🤖 AI 분석")
        lines.append(f"   {ai_text}")
    if len(buys) > 1:
        lines.append("")
        lines.append("그 외 상위")
        for b in buys[1:5]:
            bf = "🇺🇸" if b["region"] == "US" else "🇰🇷"
            lines.append(f"   {b['rank']}. {bf} {b['name']} (한달 {_fmt_pct(b.get('ret20'))})")
    notify.send("\n".join(lines))
    print("[recommend] 1등 알림 발송 완료")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="테스트용 상위 N개만")
    ap.add_argument("--kr", type=int, default=N_KR)
    ap.add_argument("--us", type=int, default=N_US)
    ap.add_argument("--no-notify", action="store_true", help="텔레그램 1등 알림 끄기")
    args = ap.parse_args()

    uni = build_universe(args.kr, args.us)
    if args.limit:
        uni = uni[: args.limit]
    print(f"universe: {len(uni)} 종목 점수화 시작…")

    start = (date.today() - timedelta(days=400)).isoformat()
    scored = []
    t0 = time.time()
    for i, s in enumerate(uni, 1):
        try:
            df = fdr.DataReader(s["code"], start)
            res = screen(df)
            if res and res["score"] > 0:
                scored.append({**s, **res})
        except Exception:
            pass
        if i % 100 == 0:
            print(f"  {i}/{len(uni)}  ({time.time()-t0:.0f}s)")

    scored.sort(key=lambda x: x["score"], reverse=True)
    buys = []
    for rank, x in enumerate(scored[:30], 1):
        buys.append({"rank": rank, **x})

    out = {
        "date": date.today().isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "universe": len(uni),
        "scored": len(scored),
        "buys": buys,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {len(scored)}개 중 상위 {len(buys)}개 저장 → {OUT.name} "
          f"({time.time()-t0:.0f}s)")

    # 1등 텔레그램 알림 (테스트(--limit)·--no-notify 시 생략)
    if not args.no_notify and not args.limit:
        notify_top(out)


if __name__ == "__main__":
    main()
