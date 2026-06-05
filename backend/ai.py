"""AI 뉴스 분석 — 헤드라인을 읽고 근거 있는 매수/매도 판단을 한국어로.

무료/유료 둘 다 지원 (키 우선순위로 자동 선택):
  1) GEMINI_API_KEY  → Google Gemini (무료 티어, 카드 불필요) ★추천
  2) ANTHROPIC_API_KEY → Claude (유료 종량과금)
  3) 둘 다 없으면 None 반환 → watcher가 키워드 기반으로 폴백

정직성:
- 환각 방지를 위해 **제공된 헤드라인·데이터에만 근거**해 분석하도록 지시한다.
- 알림당 호출이라 출력은 짧게(2~3문장) 제한한다.
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

_GEMINI_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
_GEMINI_MODEL = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
_ANTHROPIC_KEY = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
_ANTHROPIC_MODEL = (os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-8").strip()

_PLACEHOLDER = {"", "여기에_키_붙여넣기", "sk-ant-...여기에..."}


def _valid(k: str) -> bool:
    return bool(k) and k not in _PLACEHOLDER


# 키 우선순위로 제공자 결정
if _valid(_GEMINI_KEY):
    _PROVIDER = "gemini"
elif _valid(_ANTHROPIC_KEY):
    _PROVIDER = "anthropic"
else:
    _PROVIDER = None

_SYSTEM = (
    "너는 한국 주식 뉴스 분석가다. 주어진 [뉴스 헤드라인], [최근 등락], [기술적 신호]만 "
    "근거로, 그 종목이 왜 움직일 수 있는지와 지금 매수/관망/매도 중 무엇을 고려할지 "
    "한국어로 2~3문장으로 간결하게 평가하라.\n"
    "규칙:\n"
    "1) 제공된 정보에 없는 사실을 절대 지어내지 마라. 헤드라인에 근거가 없으면 "
    "'뉴스 근거가 부족하다'고 밝혀라.\n"
    "2) 단정적 수익 보장 표현 금지. '참고' 수준으로.\n"
    "3) 군더더기·서론 없이 분석 결과만 출력하라."
)

_anthropic_client = None
if _PROVIDER == "anthropic":
    try:
        import anthropic

        _anthropic_client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    except Exception as e:
        print(f"[ai] Claude 초기화 실패: {e}")
        _PROVIDER = None


def is_enabled() -> bool:
    return _PROVIDER is not None


def provider() -> str:
    return _PROVIDER or "키워드(폴백)"


def _build_user(name, code, headlines, change_pct, action, reasons) -> str:
    hl = "\n".join(f"- {h}" for h in headlines[:12])
    chg = f"{change_pct:+.1f}%" if change_pct is not None else "정보 없음"
    sig = action or "정보 없음"
    rsn = " · ".join((reasons or [])[:4]) or "정보 없음"
    return (
        f"[종목] {name} ({code})\n"
        f"[최근 등락] {chg}\n"
        f"[기술적 신호] {sig}\n"
        f"[신호 근거] {rsn}\n"
        f"[뉴스 헤드라인]\n{hl}\n\n"
        "위 정보만 근거로 평가해줘."
    )


def _gemini_analyze(user: str) -> str | None:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_GEMINI_MODEL}:generateContent?key={_GEMINI_KEY}"
    )
    body = {
        "system_instruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 500,
            "temperature": 0.4,
            # 2.5 계열은 thinking이 기본 ON → 출력 토큰을 소모해 답이 잘림. 꺼서 직접 답하게.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    r = requests.post(url, json=body, timeout=20)
    if r.status_code != 200:
        print(f"[ai] Gemini HTTP {r.status_code}: {r.text[:200]}")
        return None
    data = r.json()
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    return text or None


def _anthropic_analyze(user: str) -> str | None:
    resp = _anthropic_client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=400,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text.strip() or None


def analyze(name: str, code: str, region: str, headlines: list[str],
            change_pct: float | None, action: str | None,
            reasons: list[str] | None) -> str | None:
    """헤드라인 등을 근거로 한 줄 분석. 키 없거나 실패 시 None."""
    if _PROVIDER is None or not headlines:
        return None
    user = _build_user(name, code, headlines, change_pct, action, reasons)
    try:
        if _PROVIDER == "gemini":
            return _gemini_analyze(user)
        return _anthropic_analyze(user)
    except Exception as e:
        print(f"[ai] 분석 실패({_PROVIDER}): {e}")
        return None
