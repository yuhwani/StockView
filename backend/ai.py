"""AI 뉴스 분석 (Claude) — 헤드라인을 읽고 근거 있는 매수/매도 판단을 한국어로.

정직성:
- 환각 방지를 위해 **제공된 헤드라인·데이터에만 근거**해 분석하도록 지시한다.
- ANTHROPIC_API_KEY(.env)가 없으면 조용히 None을 반환(키워드 기반으로 폴백).

모델은 기본 claude-opus-4-8 (env ANTHROPIC_MODEL 로 변경 가능, 예: 비용 절감 시
claude-haiku-4-5). 알림당 호출이라 출력은 짧게(2~3문장) 제한한다.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()
_KEY = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
_MODEL = (os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-8").strip()
_VALID = bool(_KEY) and _KEY != "여기에_키_붙여넣기"

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

_client = None
if _VALID:
    try:
        import anthropic

        _client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수에서 읽음
    except Exception as e:
        print(f"[ai] 초기화 실패: {e}")
        _client = None


def is_enabled() -> bool:
    return _client is not None


def analyze(name: str, code: str, region: str, headlines: list[str],
            change_pct: float | None, action: str | None,
            reasons: list[str] | None) -> str | None:
    """헤드라인 등을 근거로 한 줄 분석. 키 없거나 실패 시 None."""
    if _client is None or not headlines:
        return None

    hl = "\n".join(f"- {h}" for h in headlines[:12])
    chg = f"{change_pct:+.1f}%" if change_pct is not None else "정보 없음"
    sig = action or "정보 없음"
    rsn = " · ".join((reasons or [])[:4]) or "정보 없음"
    user = (
        f"[종목] {name} ({code})\n"
        f"[최근 등락] {chg}\n"
        f"[기술적 신호] {sig}\n"
        f"[신호 근거] {rsn}\n"
        f"[뉴스 헤드라인]\n{hl}\n\n"
        "위 정보만 근거로 평가해줘."
    )

    try:
        resp = _client.messages.create(
            model=_MODEL,
            max_tokens=400,
            thinking={"type": "disabled"},
            system=[{"type": "text", "text": _SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return text.strip() or None
    except Exception as e:
        print(f"[ai] 분석 실패: {e}")
        return None
