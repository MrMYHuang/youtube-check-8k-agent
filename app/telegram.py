import logging
from typing import Any, Dict

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def _format_message(result: Dict[str, Any]) -> str:
    status = result.get("status")
    if status != "ok":
        return f"YouTube 8K Check\nStatus: {status}\nError: {result.get('error')}\n"

    has_8k = "YES" if result.get("has_8k") else "NO"
    title = result.get("video_title") or "(unknown)"
    url = result.get("video_url") or "(unknown)"
    return f"YouTube 8K Check\nTitle: {title}\nURL: {url}\n8K: {has_8k}\n"


async def send_telegram_message_async(result: Dict[str, Any]) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials not configured; skipping send")
        return

    message = _format_message(result)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": settings.telegram_chat_id, "text": message}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()


def send_telegram_message(result: Dict[str, Any]) -> None:
    import asyncio

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials not configured; skipping send")
        return

    message = _format_message(result)
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": settings.telegram_chat_id, "text": message}

    with httpx.Client(timeout=20) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
