import logging
from typing import Any, Dict

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def _format_message(result: Dict[str, Any]) -> str:
    status = result.get("status")
    if status != "ok":
        return f"YouTube 8K Check\nStatus: {status}\nError: {result.get('error')}\n"

    videos = result.get("videos", [])
    if not videos:
        return "YouTube 8K Check\nNo private videos found in recent 2 months.\n"

    lines = [f"YouTube 8K Check ({len(videos)} video{'s' if len(videos) != 1 else ''})"]
    for i, v in enumerate(videos, 1):
        has_8k = "YES ✅" if v.get("has_8k") else "NO ❌"
        url = v.get("url", "(unknown)")
        title = v.get("title", "(unknown)")
        error = v.get("error")
        line = f"\n{i}. {title}\n   URL: {url}\n   8K: {has_8k}"
        if error:
            line += f"\n   Error: {error}"
        lines.append(line)

    return "\n".join(lines) + "\n"


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
