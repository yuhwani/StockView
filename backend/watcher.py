"""실시간 이벤트 알림 워커.

관심·보유 종목(watch.json)을 주기적으로 점검해 '새로운' 재료(공시·뉴스·급등락)를
감지하면, 그 이유와 함께 매수/매도 행동 신호를 텔레그램(또는 콘솔)으로 보낸다.

실행:
  python watcher.py            # 주기 실행 (기본 10분)
  python watcher.py --once     # 한 번만 점검
  python watcher.py --test     # 테스트 알림 1건 발송
  python watcher.py --interval 300   # 5분 주기
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 콘솔 이모지/한글 출력
except Exception:
    pass

import ai
import data
import dart
import fundamentals
import model as ml
import news as news_mod
import notify
import sentiment

WATCH_FILE = HERE / "watch.json"
STATE_FILE = HERE / "watch_state.json"

PRICE_MOVE = 0.05  # 일중 ±5% 이상이면 급등락 트리거


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _material_news(title: str):
    """뉴스 제목이 강한 재료(이벤트)면 (label, tone) 반환."""
    for label, keywords, tone in sentiment._EVENTS:
        if any(k.lower() in title.lower() for k in keywords):
            return label, tone
    return None


def _dart_material(title: str):
    for label, keywords, tone in dart._EVENTS:
        if any(k in title for k in keywords):
            return label, tone
    return None


def _fmt_price(v, region):
    if v is None:
        return "-"
    return f"${v:,.2f}" if region == "US" else f"{int(round(v)):,}원"


def _build_message(code, name, region, triggers, price, chg, signal, ai_text=None) -> str:
    action = signal["action"] if signal else "관망"
    emoji = "🔴" if "매도" in action else ("🟢" if "매수" in action else "🟡")
    flag = "🇺🇸" if region == "US" else "🇰🇷"
    lines = [f"{emoji} {flag} {name} ({code}) → {action}"]
    lines.append("· 트리거: " + " / ".join(triggers))
    if price is not None:
        chg_s = f" ({chg:+.1f}%)" if chg is not None else ""
        lines.append(f"· 현재가: {_fmt_price(price, region)}{chg_s}")
    if signal and signal.get("reasons"):
        rs = [r["text"] for r in signal["reasons"][:3]]
        lines.append("· 근거: " + " · ".join(rs))
    if ai_text:
        lines.append(f"🤖 AI 분석: {ai_text}")
    lines.append("※ 참고용 신호입니다. 최종 판단·책임은 본인.")
    return "\n".join(lines)


def check_stock(code: str, state: dict) -> str | None:
    """한 종목 점검 → 알림 메시지(또는 None). 첫 점검은 baseline만 잡고 조용히."""
    region = data.get_region(code)
    name = data.get_name(code) or code
    st = state.setdefault(code, {"seen": [], "price_date": None, "first": True})
    seen = set(st["seen"])
    first = st.get("first", False)
    triggers = []

    # 1) DART 공시 (한국)
    if region == "KR":
        for d in dart.get_disclosures(code):
            key = "D|" + d["date"] + "|" + d["title"][:40]
            if key in seen:
                continue
            seen.add(key)
            m = _dart_material(d["title"])
            if m and not first:
                triggers.append(f"공시 {'호재' if m[1]=='good' else '악재'}: {m[0]}")

    # 2) 뉴스 강한 재료
    try:
        items = news_mod.get_news(code, region, name)
    except Exception:
        items = []
    for n in items:
        key = "N|" + (n.get("url") or n.get("title", ""))[:60]
        if key in seen:
            continue
        seen.add(key)
        m = _material_news(n.get("title", ""))
        if m and not first:
            triggers.append(f"뉴스 {'호재' if m[1]=='good' else '악재'}: {m[0]}")

    # 3) 가격 급등락 (당일, 하루 1회)
    price = chg = None
    try:
        df = data.get_ohlcv(code, force=True)
        price = float(df["Close"].iloc[-1])
        if len(df) > 1:
            prev = float(df["Close"].iloc[-2])
            chg = (price / prev - 1) * 100
            today = str(df.index[-1].date())
            if abs(chg) >= PRICE_MOVE * 100 and st.get("price_date") != today:
                st["price_date"] = today
                triggers.append(f"급{'등' if chg > 0 else '락'} {chg:+.1f}%")
    except Exception:
        df = None

    st["seen"] = list(seen)[-200:]  # 최근 200개만 유지
    st["first"] = False

    if not triggers:
        return None

    # 트리거 발생 → 종합 신호 계산 (이유 포함)
    signal = None
    try:
        if df is not None:
            fund = fundamentals.get_fundamentals(code, region)
            sent = sentiment.analyze(items)
            extras = {
                "valuation": fund, "supply": fund.get("supply"),
                "sentiment": sent, "dart_events": dart.detect_events(code),
                "region": region,
            }
            signal = ml.quick_signal(df, extras)
    except Exception as e:
        print(f"[watcher] {code} 신호 계산 실패: {e}")

    # AI 뉴스 분석 (키 있을 때만 — 트리거 발생 시에만 호출해 비용 절감)
    ai_text = None
    try:
        ai_text = ai.analyze(
            name, code, region, [n.get("title", "") for n in items], chg,
            signal["action"] if signal else None,
            [r["text"] for r in signal["reasons"]] if signal else None,
        )
    except Exception as e:
        print(f"[watcher] {code} AI 분석 실패: {e}")

    return _build_message(code, name, region, triggers, price, chg, signal, ai_text)


def run_once() -> int:
    codes = _load_json(WATCH_FILE, {}).get("codes", [])
    if not codes:
        print("[watcher] 감시할 종목이 없습니다 (관심종목·보유종목을 추가하세요).")
        return 0
    state = _load_json(STATE_FILE, {})
    sent = 0
    for code in codes:
        try:
            msg = check_stock(code, state)
            if msg:
                notify.send(msg)
                sent += 1
        except Exception as e:
            print(f"[watcher] {code} 점검 실패: {e}")
    _save_json(STATE_FILE, state)
    return sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=180, help="점검 주기(초)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    if args.test:
        ok = notify.send("✅ StockView 알림 테스트입니다. 이 메시지가 보이면 설정 완료!")
        print("텔레그램 발송:", ok, "(False면 .env 미설정 → 콘솔 출력)")
        return

    ch = "텔레그램" if notify.enabled() else "콘솔(텔레그램 미설정)"
    print(f"[watcher] 시작 — 주기 {args.interval}s, 알림채널: {ch}")
    if args.once:
        n = run_once()
        print(f"[watcher] 1회 점검 완료, 알림 {n}건")
        return
    while True:
        try:
            n = run_once()
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] 점검 완료, 알림 {n}건")
        except KeyboardInterrupt:
            print("\n[watcher] 종료")
            break
        except Exception as e:
            print(f"[watcher] 오류: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
