import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from .config import settings

logger = logging.getLogger(__name__)


async def _ensure_videos_page(page, studio_url: str) -> None:
    await page.goto(studio_url, wait_until="networkidle")
    if "/videos" not in page.url:
        await page.goto(studio_url.rstrip("/") + "/videos", wait_until="networkidle")


async def _find_first_private_video(page) -> Optional[Dict[str, Any]]:
    rows = page.locator("ytcp-video-row")
    await rows.first.wait_for(timeout=30_000)

    private_rows = rows.filter(has_text="Private")
    if await private_rows.count() == 0:
        return None

    first = private_rows.first
    title_locator = first.locator("#video-title")
    title = (await title_locator.inner_text()).strip()

    video_url = None
    try:
        href = await title_locator.get_attribute("href")
        if href:
            video_url = f"https://studio.youtube.com{href}"
    except Exception:
        pass

    await title_locator.click()
    return {"title": title, "url": video_url}


async def _open_watch_page(context, page) -> Optional[Any]:
    try:
        # YouTube Studio shows a "Video link" label with the URL beneath it.
        label = page.get_by_text("Video link", exact=True)
        await label.wait_for(timeout=20_000)

        container = label.locator("..")
        link_loc = container.locator(
            "a[href*='youtu.be'], a[href*='youtube.com/watch']"
        ).first
        await link_loc.wait_for(timeout=10_000)
        href = await link_loc.get_attribute("href")
        if not href:
            return None

        watch_page = await context.new_page()
        await watch_page.goto(href, wait_until="networkidle")
        return watch_page
    except PlaywrightTimeoutError:
        return None


async def _check_8k_in_player(page) -> bool:
    await page.wait_for_selector("#movie_player", timeout=30_000)
    # Ensure player has focus and controls are visible.
    await page.click("#movie_player", timeout=10_000)
    settings_btn = page.locator("button.ytp-settings-button")
    await settings_btn.wait_for(timeout=10_000)
    await settings_btn.click(force=True)
    await page.wait_for_selector(".ytp-panel-menu", timeout=10_000)
    quality_item = (
        page.locator(".ytp-panel-menu .ytp-menuitem").filter(has_text="Quality").first
    )
    await quality_item.click()
    await page.wait_for_selector(".ytp-panel-menu", timeout=10_000)

    items = page.locator(".ytp-panel-menu .ytp-menuitem")
    count = await items.count()
    for i in range(count):
        text = (await items.nth(i).inner_text()).strip()
        if "4320p" in text or "8K" in text or "8k" in text:
            return True
    return False


async def run_check_8k() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "video_title": None,
        "video_url": None,
        "has_8k": False,
        "status": "unknown",
        "error": None,
    }

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=settings.user_data_dir,
            headless=settings.headless,
            slow_mo=settings.slow_mo_ms,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await context.new_page()

        try:
            await _ensure_videos_page(page, settings.studio_url)
            private_video = await _find_first_private_video(page)
            if not private_video:
                result["status"] = "no_private_videos"
                return result

            result["video_title"] = private_video["title"]

            watch_page = await _open_watch_page(context, page)
            if watch_page is None:
                result["status"] = "watch_page_not_found"
                return result

            result["video_url"] = watch_page.url
            result["has_8k"] = await _check_8k_in_player(watch_page)
            result["status"] = "ok"
            return result
        except PlaywrightTimeoutError as exc:
            logger.exception("Playwright timeout")
            result["status"] = "timeout"
            result["error"] = str(exc)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error")
            result["status"] = "error"
            result["error"] = str(exc)
            return result
        finally:
            await context.close()


def run_check_8k_sync() -> Dict[str, Any]:
    return asyncio.run(run_check_8k())


def run_check_8k_json() -> str:
    return json.dumps(run_check_8k_sync())
