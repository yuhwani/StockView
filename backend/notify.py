"""알림 발송 — 텔레그램 봇 (없으면 콘솔 출력으로 폴백).

.env 에 다음을 넣으면 폰으로 알림이 온다:
  TELEGRAM_BOT_TOKEN=...   (BotFather에서 발급)
  TELEGRAM_CHAT_ID=...     (본인 chat id)
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()
_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
_CHAT = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()


def enabled() -> bool:
    return bool(_TOKEN and _CHAT)


def send(text: str) -> bool:
    """텔레그램으로 전송. 설정 없으면 콘솔에 출력."""
    if not enabled():
        print("\n────── [알림 · 콘솔] ──────")
        print(text)
        print("───────────────────────────\n")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            data={"chat_id": _CHAT, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        return r.ok
    except Exception as e:
        print(f"[notify] 텔레그램 전송 실패: {e}")
        return False
