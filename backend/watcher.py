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
import alertconfig
import data
import dart
import fundamentals
import model as ml
import news as news_mod
import notify
import sentiment

WATCH_FILE = HERE / "watch.json"
STATE_FILE = HERE / "watch_state.json"


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
    arrow = "▲" if (chg or 0) > 0 else ("▼" if (chg or 0) < 0 else "·")

    lines = [f"{emoji} {action}  |  {flag} {name} ({code})"]
    if price is not None:
        chg_s = f"   {arrow} {chg:+.1f}% (전일대비)" if chg is not None else ""
        lines.append(f"💰 {_fmt_price(price, region)}{chg_s}")

    lines.append("")
    lines.append("🔔 감지된 이벤트")
    for t in triggers:
        lines.append(f"   • {t}")

    if signal and signal.get("reasons"):
        # 방향성(매수/매도) 근거를 우선 노출, 중립은 보조. 최대 5개.
        rs = signal["reasons"]
        directional = [r for r in rs if r.get("dir") in ("up", "down")]
        shown = (directional or rs)[:5]
        lines.append("")
        lines.append("📊 판단 근거")
        for r in shown:
            lines.append(f"   • {r['text']}")

    if ai_text:
        lines.append("")
        lines.append("🤖 AI 분석")
        lines.append(f"   {ai_text}")

    return "\n".join(lines)


_BUY_ACTIONS = ("매수 우위", "약한 매수")
_SELL_ACTIONS = ("매도 우위", "약한 매도")


def _buy_worthy(signal) -> bool:
    return bool(signal) and signal.get("action") in _BUY_ACTIONS


def _sell_worthy(signal) -> bool:
    return bool(signal) and signal.get("action") in _SELL_ACTIONS


def _volume_surge(df, mult: float = 1.5) -> bool:
    """오늘 거래량이 직전 20일 평균의 mult배 이상이면 '거래량 동반'(오늘 터진 것)."""
    try:
        v = df["Volume"].astype(float)
        base = float(v.iloc[-21:-1].mean())  # 오늘 제외 직전 20일 평균
        return base > 0 and float(v.iloc[-1]) / base >= mult
    except Exception:
        return False


def _summary_line(action, region, name, triggers, prefix="") -> str:
    """요약(digest) 메시지용 한 줄. 예: '🟢 약한 매수 🇰🇷 삼성전자 — 급등 +5.2% 외 1건'."""
    act = action or "관망"
    emoji = "🔴" if "매도" in act else ("🟢" if "매수" in act else "🟡")
    flag = "🇺🇸" if region == "US" else "🇰🇷"
    extra = f" 외 {len(triggers) - 1}건" if len(triggers) > 1 else ""
    head = (triggers[0] if triggers else "")
    return f"{prefix}{emoji} {act} {flag} {name} — {head}{extra}"


def _flipped(prev_action, signal) -> bool:
    """직전 알림의 행동과 지금 신호가 매수↔매도로 뒤집혔는지."""
    now = (signal or {}).get("action")
    if not prev_action or not now:
        return False
    pb, ps = prev_action in _BUY_ACTIONS, prev_action in _SELL_ACTIONS
    nb, ns = now in _BUY_ACTIONS, now in _SELL_ACTIONS
    return (pb and ns) or (ps and nb)


def _signal_for(code: str, region: str, df):
    """종목 종합 신호 계산(후속 점검용). 실패 시 None."""
    try:
        fund = fundamentals.get_fundamentals(code, region)
        try:
            items = news_mod.get_news(code, region, data.get_name(code) or code)
        except Exception:
            items = []
        extras = {
            "valuation": fund, "supply": fund.get("supply"),
            "sentiment": sentiment.analyze(items), "dart_events": dart.detect_events(code),
            "region": region, "regime": data.get_market_regime(),
        }
        return ml.quick_signal(df, extras)
    except Exception as e:
        print(f"[watcher] {code} 후속 신호 계산 실패: {e}")
        return None


def _followup_check(code: str, st: dict, today_cal: str, followup_pct: float) -> str | None:
    """오늘 이미 알림한 종목 — '강한 후속 사건'이면 한 번 더 알림.

    후속 발송 조건: ① 새 공시/뉴스 재료, ② 알림가 대비 추가 ±followup_pct% 변동,
    ③ 신호 반전(매수↔매도). 하루 후속은 최대 3회로 제한(스팸 방지).
    """
    if st.get("followup_date") != today_cal:
        st["followup_date"], st["followup_n"] = today_cal, 0
    if st.get("followup_n", 0) >= 3:
        return None

    region = data.get_region(code)
    name = data.get_name(code) or code
    seen = set(st.get("seen", []))
    new_triggers = []

    if region == "KR":  # 새 공시
        for d in dart.get_disclosures(code):
            key = "D|" + d["date"] + "|" + d["title"][:40]
            if key in seen:
                continue
            seen.add(key)
            m = _dart_material(d["title"])
            if m:
                new_triggers.append(f"공시 {'호재' if m[1] == 'good' else '악재'}: {m[0]}")
    try:  # 새 뉴스 재료
        items = news_mod.get_news(code, region, name)
    except Exception:
        items = []
    for n in items:
        key = "N|" + (n.get("url") or n.get("title", ""))[:60]
        if key in seen:
            continue
        seen.add(key)
        m = _material_news(n.get("title", ""))
        if m:
            new_triggers.append(f"뉴스 {'호재' if m[1] == 'good' else '악재'}: {m[0]}")

    df = price = None
    add = 0.0
    try:
        df = data.get_ohlcv(code, force=True)
        price = float(df["Close"].iloc[-1])
        ap = st.get("alerted_price")
        if ap:
            add = (price / ap - 1) * 100  # 알림가 대비 추가 변동
    except Exception:
        pass
    st["seen"] = list(seen)[-200:]

    big_move = abs(add) >= followup_pct
    if not new_triggers and not big_move:
        return None  # 강한 후속 사건 없음 → 조용히

    signal = _signal_for(code, region, df) if df is not None else None
    flipped = _flipped(st.get("alerted_action"), signal)

    triggers = list(new_triggers)
    if add >= followup_pct:
        triggers.append(f"알림 후 추가 +{add:.1f}% 상승")
    elif add <= -followup_pct:
        triggers.append(f"알림 후 추가 {add:.1f}% 급락")
    if flipped:
        triggers.append(f"신호 반전: {st.get('alerted_action')} → {signal.get('action')}")
    if not triggers:
        return None

    chg = None
    try:
        chg = (price / float(df["Close"].iloc[-2]) - 1) * 100
    except Exception:
        pass
    if price is not None:
        st["alerted_price"] = price
    action = signal.get("action") if signal else None
    if action:
        st["alerted_action"] = action
    st["followup_n"] = st.get("followup_n", 0) + 1
    body = _build_message(code, name, region, triggers, price, chg, signal, None)
    return {
        "msg": "🔁 [후속] 알림 후 새로운 변화\n\n" + body,
        "line": _summary_line(action, region, name, triggers, prefix="🔁 "),
    }


def check_stock(code: str, state: dict, move_pct: float = 5.0,
                buy_focus: bool = True, followup_pct: float = 5.0) -> str | None:
    """한 종목 점검 → 알림 메시지(또는 None). 첫 점검은 baseline만 잡고 조용히.

    buy_focus=True면 급등은 '매수 신호+거래량 동반'일 때만, 급락은 '매도 신호'일 때만
    알림에 포함(살 만한/팔 만한 것만). 공시·뉴스 재료는 그대로(초기 catalyst).
    """
    st = state.setdefault(code, {"seen": [], "price_date": None, "first": True})
    today_cal = str(date.today())
    if st.get("alerted_date") == today_cal:
        # 오늘 이미 알림함 → 강한 후속 사건(추가 급변동·새 공시·신호 반전)일 때만 한 번 더
        return _followup_check(code, st, today_cal, followup_pct)
    region = data.get_region(code)
    name = data.get_name(code) or code
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

    # 3) 가격 급등락 (당일, 하루 1회) — buy_focus면 신호로 한 번 더 거른다
    price = chg = None
    price_spike = None  # ("up"/"down", 트리거 문구)
    try:
        df = data.get_ohlcv(code, force=True)
        price = float(df["Close"].iloc[-1])
        if len(df) > 1:
            prev = float(df["Close"].iloc[-2])
            chg = (price / prev - 1) * 100
            today = str(df.index[-1].date())
            if abs(chg) >= move_pct and st.get("price_date") != today:
                st["price_date"] = today
                price_spike = ("up" if chg > 0 else "down",
                               f"급{'등' if chg > 0 else '락'} {chg:+.1f}%")
    except Exception:
        df = None

    st["seen"] = list(seen)[-200:]  # 최근 200개만 유지
    st["first"] = False

    if not triggers and not price_spike:
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
                "region": region, "regime": data.get_market_regime(),
            }
            signal = ml.quick_signal(df, extras)
    except Exception as e:
        print(f"[watcher] {code} 신호 계산 실패: {e}")

    # 급등락을 알림에 포함할지 결정 (buy_focus: 살 만한 급등 / 팔 만한 급락만)
    if price_spike:
        direction, text = price_spike
        if not buy_focus:
            triggers.append(text)
        elif direction == "up" and _buy_worthy(signal) and _volume_surge(df):
            triggers.append(text)
        elif direction == "down" and _sell_worthy(signal):
            triggers.append(text)

    if not triggers:
        return None  # 급등락이 신호 미달로 걸러지고 다른 재료도 없음

    # AI 뉴스 분석 (키 있을 때만 — 트리거 발생 시에만 호출해 비용 절감)
    ai_text = None
    try:
        fund = fundamentals.get_fundamentals(code, region)
        context = {
            "roe": fund.get("roe"), "op_margin": fund.get("op_margin"),
            "debt_ratio": fund.get("debt_ratio"), "rev_growth": fund.get("rev_growth"),
            "per": fund.get("per"), "pbr": fund.get("pbr"), "sector": fund.get("sector"),
            "disclosures": [d["title"] for d in dart.get_disclosures(code)[:5]] if region == "KR" else [],
        }
        ai_text = ai.analyze(
            name, code, region, [n.get("title", "") for n in items], chg,
            signal["action"] if signal else None,
            [r["text"] for r in signal["reasons"]] if signal else None,
            context=context,
        )
    except Exception as e:
        print(f"[watcher] {code} AI 분석 실패: {e}")

    # 오늘 알림 보냄 표시 + 후속 비교 기준(가격·행동) 저장
    st["alerted_date"] = today_cal
    if price is not None:
        st["alerted_price"] = price
    action = signal.get("action") if signal else None
    st["alerted_action"] = action
    return {
        "msg": _build_message(code, name, region, triggers, price, chg, signal, ai_text),
        "line": _summary_line(action, region, name, triggers),
    }


# ETF·ETN·레버리지/인버스는 '발굴'에서 제외 (종목 발굴 기회가 아님)
_ETF_HINTS = ("KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO", "KOSEF", "KIWOOM",
              "TIMEFOLIO", "ACE ", "SOL ", "PLUS ", "RISE ", "WON ", "마이티",
              "인버스", "레버리지", "선물", "ETN", " 2X", " 3X",
              "ProShares", "Direxion", "iShares", "SPDR", "Vanguard", "Invesco",
              "ETF", "Leveraged", "Bull ", "Bear ")


def _is_etf(name: str) -> bool:
    return any(h.lower() in name.lower() for h in _ETF_HINTS)


def _scan_candidates(cfg: dict) -> list[dict]:
    """관심목록 외 발굴 후보. '이미 급등'이 아니라 '막 오르기 시작(+lo~hi%) + 거래대금 활발'
    순으로 추려, 강한 매수 신호가 뜨는 종목을 일찍 잡는다. (과열 hi%↑는 추격 방지로 제외)
    """
    region = cfg.get("discovery_region", "KR")
    lo = cfg.get("discovery_move_pct", 3.0)        # 시작 최소 상승
    hi = cfg.get("discovery_max_gain_pct", 15.0)   # 이미 많이 오른 건 제외
    min_cap = cfg.get("discovery_min_marcap_eok", 3000) * 1e8  # 억원 → 원
    out = []
    try:
        if region == "US":
            df = data.get_us_marcap()
            chg_col, sort_col = "ChangeRatio", ("Amount" if "Amount" in (df.columns if df is not None else []) else "Marcap")
            if df is not None and not df.empty:
                d = df[(df["Marcap"] >= min_cap) & (df[chg_col] >= lo) & (df[chg_col] <= hi)]
                d = d.sort_values(sort_col, ascending=False).head(40)  # 거래대금 활발한 순
                for r in d.itertuples():
                    if _is_etf(str(r.Name)):
                        continue
                    out.append({"code": str(r.Code), "name": str(r.Name),
                                "region": "US", "chg": float(getattr(r, chg_col))})
        else:
            krx = data._krx()
            if data._krx_ok(krx):
                sc = "Amount" if "Amount" in krx.columns else "Marcap"
                d = krx[(krx["Marcap"] >= min_cap) & (krx["ChagesRatio"] >= lo) & (krx["ChagesRatio"] <= hi)]
                d = d.sort_values(sc, ascending=False).head(40)  # 거래대금 활발한 순
                for r in d.itertuples():
                    if _is_etf(str(r.Name)):
                        continue
                    out.append({"code": str(r.Code), "name": str(r.Name),
                                "region": "KR", "chg": float(r.ChagesRatio)})
    except Exception as e:
        print(f"[watcher] 발굴 후보 스캔 실패: {e}")
    return out[:25]


def discovery_scan(state: dict, cfg: dict) -> list[str]:
    """관심목록 '외' 급등 종목을 발굴해 알림 메시지를 만든다 (종목당 하루 1회)."""
    watch = set(_load_json(WATCH_FILE, {}).get("codes", []))
    dstate = state.setdefault("_discovery", {})
    today = str(date.today())
    cap = cfg.get("discovery_max_per_cycle", 3)
    msgs = []
    for c in _scan_candidates(cfg):
        if len(msgs) >= cap:
            break
        code, region = c["code"], c["region"]
        if code in watch or dstate.get(code) == today:
            continue
        dstate[code] = today  # 오늘 이미 발굴 → 중복 방지
        try:
            df = data.get_ohlcv(code, force=True)
            fund = fundamentals.get_fundamentals(code, region)
            extras = {"valuation": fund, "supply": fund.get("supply"),
                      "region": region, "regime": data.get_market_regime()}
            signal = ml.quick_signal(df, extras)
            # 발굴은 더 엄격하게 — '매수 우위'(여러 근거가 강하게 정렬) + 거래량 동반만
            strong = bool(signal) and signal.get("action") == "매수 우위"
            if cfg.get("buy_focus", True) and not (strong and _volume_surge(df)):
                continue
            # AI 종합 분석 (발굴은 드물고 고품질이라 비용 부담 적음 → 설득력 ↑)
            ai_text = None
            try:
                items = news_mod.get_news(code, region, c["name"])
                context = {
                    "roe": fund.get("roe"), "op_margin": fund.get("op_margin"),
                    "debt_ratio": fund.get("debt_ratio"), "rev_growth": fund.get("rev_growth"),
                    "per": fund.get("per"), "pbr": fund.get("pbr"), "sector": fund.get("sector"),
                    "disclosures": [d["title"] for d in dart.get_disclosures(code)[:5]] if region == "KR" else [],
                }
                ai_text = ai.analyze(c["name"], code, region,
                                     [n.get("title", "") for n in items], c["chg"],
                                     signal["action"], [r["text"] for r in signal["reasons"]],
                                     context=context)
            except Exception as e:
                print(f"[watcher] 발굴 {code} AI 실패: {e}")
            price = float(df["Close"].iloc[-1])
            trig = [f"관심목록 외 매수신호 포착 (오늘 +{c['chg']:.1f}%)"]
            body = _build_message(code, c["name"], region, trig, price, c["chg"], signal, ai_text)
            action = signal.get("action") if signal else "매수 우위"
            msgs.append({
                "msg": "🔎 [발굴] 강한 매수 신호 포착\n\n" + body,
                "line": _summary_line(action, region, c["name"], trig, prefix="🔎 "),
            })
        except Exception as e:
            print(f"[watcher] 발굴 {code} 실패: {e}")
    return msgs


def _parse_hours(s) -> list[int]:
    out = [int(t) for t in str(s).split(",") if t.strip().isdigit() and 0 <= int(t) <= 23]
    return sorted(set(out)) or [12, 18]


def _digest_message(hour: int, lines: list[str]) -> str:
    label = "점심" if hour < 15 else "퇴근"
    head = f"📋 [{label} 요약 · {hour}시] 오늘 포착 {len(lines)}건"
    return head + "\n\n" + "\n".join(lines) + "\n\n· 근거·AI 분석은 앱 종목 상세에서 확인하세요."


def _maybe_send_digest(dg: dict, cfg: dict) -> int:
    """정해진 시각이 지났고 아직 안 보낸 요약이 있으면 한 통으로 발송."""
    now_h = datetime.now().hour
    sent = 0
    for h in _parse_hours(cfg.get("digest_hours", "12,18")):
        tag = str(h)
        if now_h >= h and tag not in dg["sent"]:
            dg["sent"].append(tag)
            if dg["lines"]:
                notify.send(_digest_message(h, dg["lines"]))
                dg["lines"] = []
                sent += 1
    return sent


def run_once(cfg: dict | None = None) -> int:
    cfg = cfg or alertconfig.load()
    mode = cfg.get("alert_mode", "digest")
    realtime = mode in ("realtime", "both")
    digest = mode in ("digest", "both")
    state = _load_json(STATE_FILE, {})
    sent = 0
    found = []  # 이번 주기 포착 [{msg, line}, ...]

    # 1) 관심·보유 종목 점검
    for code in _load_json(WATCH_FILE, {}).get("codes", []):
        try:
            item = check_stock(code, state, cfg.get("price_move_pct", 5.0),
                               cfg.get("buy_focus", True),
                               cfg.get("followup_move_pct", 5.0))
            if item:
                found.append(item)
        except Exception as e:
            print(f"[watcher] {code} 점검 실패: {e}")

    # 2) 관심목록 외 발굴
    if cfg.get("discovery_enabled"):
        try:
            found.extend(discovery_scan(state, cfg))
        except Exception as e:
            print(f"[watcher] 발굴 스캔 실패: {e}")

    # 실시간 발송 (모드 realtime/both)
    if realtime:
        for it in found:
            notify.send(it["msg"]); sent += 1

    # 요약 버퍼 적재 + 정해진 시각에 한 통 발송 (모드 digest/both)
    if digest:
        dg = state.setdefault("_digest", {"date": None, "lines": [], "sent": []})
        today = str(date.today())
        if dg.get("date") != today:
            dg["date"], dg["lines"], dg["sent"] = today, [], []
        dg["lines"].extend(it["line"] for it in found)
        sent += _maybe_send_digest(dg, cfg)

    _save_json(STATE_FILE, state)
    return sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=0, help="점검 주기(초). 0이면 설정값 사용")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    if args.test:
        ok = notify.send("✅ StockView 알림 테스트입니다. 이 메시지가 보이면 설정 완료!")
        print("텔레그램 발송:", ok, "(False면 .env 미설정 → 콘솔 출력)")
        return

    cfg = alertconfig.load()
    ch = "텔레그램" if notify.enabled() else "콘솔(텔레그램 미설정)"
    _mode = {"digest": f"요약({cfg.get('digest_hours')}시)",
             "realtime": "실시간", "both": "실시간+요약"}.get(cfg.get("alert_mode", "digest"), "요약")
    disc = ("발굴 ON" if cfg.get("discovery_enabled") else "발굴 OFF") + f", 알림={_mode}"
    if args.once:
        print(f"[watcher] 1회 점검 — 알림채널: {ch}, {disc}")
        n = run_once(cfg)
        print(f"[watcher] 1회 점검 완료, 알림 {n}건")
        return

    interval = args.interval or cfg.get("interval_sec", 180)
    print(f"[watcher] 시작 — 주기 {interval}s, 알림채널: {ch}, {disc}")
    while True:
        cfg = alertconfig.load()  # 매 주기마다 설정 다시 읽기 (재시작 없이 반영)
        try:
            n = run_once(cfg)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] 점검 완료, 알림 {n}건")
        except KeyboardInterrupt:
            print("\n[watcher] 종료")
            break
        except Exception as e:
            print(f"[watcher] 오류: {e}")
        time.sleep(args.interval or cfg.get("interval_sec", 180))


if __name__ == "__main__":
    main()
