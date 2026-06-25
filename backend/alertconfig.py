"""알림 설정 — 사용자가 UI에서 바꾸는 임계값·발굴 옵션을 alert_config.json에 저장.

워커는 매 점검 주기마다 이 파일을 다시 읽어, 재시작 없이 설정이 즉시 반영된다.
"""
from __future__ import annotations

import json
from pathlib import Path

_FILE = Path(__file__).resolve().parent / "alert_config.json"

# 키: (기본값, 타입, 최소, 최대) — 검증·클램프용
_SPEC = {
    "interval_sec": (180, int, 60, 3600),          # 점검 주기(초)
    "alert_mode": ("digest", str, None, None),      # realtime / digest(정해진 시간 요약) / both
    "digest_hours": ("12,18", str, None, None),     # 요약 발송 시각(시, 콤마구분) 예: 12,18
    "price_move_pct": (5.0, float, 1.0, 30.0),     # 관심·보유 급등락 알림 임계(±%)
    "followup_move_pct": (5.0, float, 2.0, 20.0),  # 알림 후 추가로 ±이만큼 더 움직이면 후속 알림
    "buy_focus": (True, bool, None, None),          # 급등·발굴은 매수 신호+거래량일 때만(노이즈↓)
    "discovery_enabled": (True, bool, None, None),  # 관심목록 외 발굴 알림 on/off
    "discovery_realtime": (True, bool, None, None),  # 발굴은 요약과 별개로 항상 실시간 발송
    "discovery_move_pct": (3.0, float, 1.0, 30.0),  # 발굴 '시작' 최소 상승(+%) — 낮을수록 일찍 포착
    "discovery_max_gain_pct": (15.0, float, 5.0, 60.0),  # 이미 이만큼 오른 건 제외(추격 방지)
    "discovery_min_marcap_eok": (3000, int, 100, 1000000),  # 발굴 최소 시총(억원)
    "discovery_region": ("KR", str, None, None),    # 발굴 대상 시장 (KR/US)
    "discovery_max_per_cycle": (3, int, 1, 10),     # 한 점검당 최대 발굴 알림 수
}

DEFAULTS = {k: v[0] for k, v in _SPEC.items()}


def _coerce(key, value):
    default, typ, lo, hi = _SPEC[key]
    try:
        if typ is bool:
            v = bool(value)
        elif typ is int:
            v = int(float(value))
        elif typ is float:
            v = float(value)
        else:  # str
            v = str(value).strip()
            if key == "discovery_region" and v not in ("KR", "US"):
                return default
            if key == "alert_mode" and v not in ("realtime", "digest", "both"):
                return default
            return v
    except (TypeError, ValueError):
        return default
    if lo is not None:
        v = max(lo, min(hi, v))
    return v


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        raw = json.loads(_FILE.read_text(encoding="utf-8"))
        for k in _SPEC:
            if k in raw:
                cfg[k] = _coerce(k, raw[k])
    except Exception:
        pass
    return cfg


def save(patch: dict) -> dict:
    cfg = load()
    for k, v in (patch or {}).items():
        if k in _SPEC:
            cfg[k] = _coerce(k, v)
    _FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg
