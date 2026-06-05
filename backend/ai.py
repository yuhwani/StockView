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
    "너는 한국·미국 주식 분석가다. 주어진 [재무], [공시], [뉴스 헤드라인], [최근 등락], "
    "[기술적 신호]만 근거로 다음을 한국어 3~4문장으로 평가하라: "
    "① 지금 이 종목의 핵심 포인트, ② 사업 체력·경쟁력(이익률·ROE·성장성·재무안정성으로 판단), "
    "③ 지금 매수/관망/매도 중 무엇을 고려할지.\n"
    "규칙:\n"
    "1) 제공된 정보에 없는 사실(경영진 역량·경제적 해자·시장점유율 등)을 추측해 단정하지 마라. "
    "재무 수치나 뉴스로 뒷받침될 때만 언급하고, 근거가 없으면 그 항목은 말하지 마라.\n"
    "2) 일반인도 이해하도록 쉬운 말로. 전문용어는 풀어서.\n"
    "3) 단정적 수익 보장 표현 금지. '참고' 수준으로.\n"
    "4) 마크다운 기호(**, #, - 등) 쓰지 말고 일반 문장으로만. 군더더기·서론 없이 분석만 출력."
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


def _build_user(name, code, headlines, change_pct, action, reasons, context=None) -> str:
    context = context or {}
    hl = "\n".join(f"- {h}" for h in headlines[:12]) or "- (수집된 헤드라인 없음)"
    chg = f"{change_pct:+.1f}%" if change_pct is not None else "정보 없음"
    sig = action or "정보 없음"
    rsn = " · ".join((reasons or [])[:5]) or "정보 없음"

    fin = []
    for label, key, unit in [("ROE", "roe", "%"), ("영업이익률", "op_margin", "%"),
                             ("부채비율", "debt_ratio", "%"), ("매출성장(전년比)", "rev_growth", "%"),
                             ("PER", "per", "배"), ("PBR", "pbr", "배")]:
        v = context.get(key)
        if v is not None:
            fin.append(f"{label} {v:g}{unit}")
    fin_s = ", ".join(fin) or "정보 없음"

    sector = context.get("sector")
    head = f"[종목] {name} ({code})" + (f" · 업종 {sector}" if sector else "")
    disc = context.get("disclosures") or []
    disc_s = "\n".join(f"- {d}" for d in disc[:5]) or "- (최근 주요 공시 없음)"

    return (
        f"{head}\n"
        f"[재무] {fin_s}\n"
        f"[최근 등락] {chg}\n"
        f"[기술적 신호] {sig} (근거: {rsn})\n"
        f"[공시]\n{disc_s}\n"
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
            "maxOutputTokens": 700,
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
        max_tokens=600,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text.strip() or None


def analyze(name: str, code: str, region: str, headlines: list[str],
            change_pct: float | None, action: str | None,
            reasons: list[str] | None, context: dict | None = None) -> str | None:
    """헤드라인·재무·공시를 근거로 짧은 분석. 키 없거나 근거 없으면 None."""
    if _PROVIDER is None or (not headlines and not context):
        return None
    user = _build_user(name, code, headlines, change_pct, action, reasons, context)
    try:
        if _PROVIDER == "gemini":
            return _gemini_analyze(user)
        return _anthropic_analyze(user)
    except Exception as e:
        print(f"[ai] 분석 실패({_PROVIDER}): {e}")
        return None
