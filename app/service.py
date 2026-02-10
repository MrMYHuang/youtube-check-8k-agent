import asyncio
import logging
from typing import Any, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from tzlocal import get_localzone

from .agent import run_agent
from .config import settings
from .telegram import send_telegram_message_async

logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube 8K Agent")
_lock = asyncio.Lock()
_scheduler: AsyncIOScheduler | None = None


async def _run_task() -> Dict[str, Any]:
    async with _lock:
        result = await run_agent()
        await send_telegram_message_async(result)
        return result


@app.on_event("startup")
async def startup_event() -> None:
    global _scheduler
    tz = settings.schedule_tz or str(get_localzone())
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        _run_task,
        "cron",
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
        id="youtube_8k_daily",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started for %s %02d:%02d",
        tz,
        settings.schedule_hour,
        settings.schedule_minute,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _scheduler:
        _scheduler.shutdown()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
async def run_now() -> Dict[str, Any]:
    try:
        result = await _run_task()
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Run failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
