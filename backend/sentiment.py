"""뉴스 헤드라인 감성 분석 + 재료(이벤트) 키워드 감지 — 사전(lexicon) 방식.

LLM 없이 무료로 동작. 정교하진 않지만 "헤드라인이 전반적으로 호재인지 악재인지",
그리고 "자사주 매입·증설·최초 기술 같은 강한 재료가 있는지"를 거칠게 잡아낸다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

# 긍정/부정 단어 (한국어 + 영어)
_POS = [
    # KR
    "상승", "급등", "강세", "신고가", "최고가", "돌파", "호재", "흑자", "수주",
    "계약", "최대", "성장", "개선", "확대", "호실적", "깜짝", "수혜", "신제품",
    "목표가 상향", "상향", "순매수", "반등", "기대", "역대", "사상 최대",
    # EN
    "surge", "soar", "jump", "rally", "beat", "record", "high", "upgrade",
    "buy", "growth", "profit", "gain", "strong", "top", "launch", "rise", "win",
]
_NEG = [
    # KR
    "하락", "급락", "약세", "적자", "손실", "우려", "리스크", "하향", "감소",
    "축소", "부진", "쇼크", "악재", "순매도", "영업손실", "감자", "횡령",
    "소송", "제재", "경고", "철회", "최저", "급감", "위기",
    # EN
    "plunge", "drop", "fall", "miss", "loss", "downgrade", "sell", "weak",
    "cut", "lawsuit", "probe", "warning", "concern", "decline", "slump", "risk",
]

# 강한 재료(이벤트) — 사용자가 중요하게 본 항목들
_EVENTS = [
    ("자사주 매입", ["자사주", "자기주식", "buyback", "repurchase"], "good"),
    ("신규 투자·증설", ["증설", "신규 투자", "신규투자", "시설투자", "공장 신설",
                    "capacity", "expansion", "new plant"], "good"),
    ("최초·최고 기술", ["세계 최초", "국내 최초", "업계 최초", "세계 최고",
                   "world first", "world's first", "breakthrough"], "good"),
    ("대형 수주·계약", ["수주", "공급 계약", "대규모 계약", "contract", "order win",
                   "deal"], "good"),
    ("악재(소송·감자 등)", ["소송", "횡령", "감자", "상장폐지", "제재", "lawsuit",
                     "fraud", "delisting", "investigation"], "bad"),
]


def _hits(text: str, words: list[str]) -> int:
    low = text.lower()
    return sum(1 for w in words if w.lower() in low)


def analyze(items: list[dict]) -> dict:
    """뉴스 리스트 → 감성 점수(-1~1) + 감지된 재료 태그."""
    if not items:
        return {"score": 0.0, "pos": 0, "neg": 0, "total": 0, "events": []}

    pos = neg = 0
    for it in items:
        title = it.get("title", "")
        p, n = _hits(title, _POS), _hits(title, _NEG)
        if p > n:
            pos += 1
        elif n > p:
            neg += 1

    total = len(items)
    score = (pos - neg) / total  # -1 ~ 1

    # 언론 노출 빈도: 최근 7일 기사 수
    cutoff = datetime.now() - timedelta(days=7)
    recent = 0
    for it in items:
        dt = it.get("datetime", "")
        try:
            if datetime.strptime(dt[:16], "%Y-%m-%d %H:%M") >= cutoff:
                recent += 1
        except (ValueError, TypeError):
            pass

    # 재료(이벤트) 감지
    blob = " ".join(it.get("title", "") for it in items)
    events = []
    for label, keywords, tone in _EVENTS:
        if _hits(blob, keywords):
            events.append({"label": label, "tone": tone})

    return {
        "score": round(score, 3),
        "pos": pos,
        "neg": neg,
        "total": total,
        "recent7d": recent,
        "events": events,
    }
