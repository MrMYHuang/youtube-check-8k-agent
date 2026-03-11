import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from .config import settings

logger = logging.getLogger(__name__)

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_upload_date(text: str) -> Optional[datetime]:
    """Parse a date from YouTube Studio row text."""
    # Relative: "N unit(s) ago"
    m = re.search(
        r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
        text,
        re.IGNORECASE,
    )
    if m:
        num = int(m.group(1))
        unit = m.group(2).lower()
        now = datetime.now()
        deltas = {
            "second": timedelta(seconds=num),
            "minute": timedelta(minutes=num),
            "hour": timedelta(hours=num),
            "day": timedelta(days=num),
            "week": timedelta(weeks=num),
            "month": timedelta(days=num * 30),
            "year": timedelta(days=num * 365),
        }
        return now - deltas.get(unit, timedelta())

    # Absolute: "Mar 10, 2026" or "March 10, 2026"
    m = re.search(r"([A-Za-z]{3,9})\s+(\d{1,2}),\s+(\d{4})", text)
    if m:
        month_str = m.group(1)[:3].lower()
        day = int(m.group(2))
        year = int(m.group(3))
        month = _MONTH_ABBR.get(month_str)
        if month:
            return datetime(year, month, day)

    return None


def _extract_video_id(href: str) -> Optional[str]:
    """Extract video ID from a YouTube Studio href like '/video/VIDEO_ID/edit'."""
    m = re.search(r"/video/([^/]+)", href)
    return m.group(1) if m else None


async def _ensure_videos_page(page, studio_url: str) -> None:
    await page.goto(studio_url, wait_until="networkidle")
    if "/videos" not in page.url:
        await page.goto(studio_url.rstrip("/") + "/videos", wait_until="networkidle")


async def _collect_private_videos(
    page, cutoff: datetime
) -> List[Dict[str, Any]]:
    """Scroll through the video list and collect private videos within the cutoff."""
    videos: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    rows_locator = page.locator("ytcp-video-row")
    await rows_locator.first.wait_for(timeout=30_000)

    max_scrolls = 50
    for _ in range(max_scrolls):
        count = await rows_locator.count()
        found_old = False

        for i in range(count):
            row = rows_locator.nth(i)
            row_text = await row.inner_text()

            if "Private" not in row_text:
                continue

            title_locator = row.locator("#video-title")
            href = await title_locator.get_attribute("href")
            if not href:
                continue

            video_id = _extract_video_id(href)
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            upload_date = _parse_upload_date(row_text)
            if upload_date and upload_date < cutoff:
                found_old = True
                continue

            title = (await title_locator.inner_text()).strip()
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            videos.append({"title": title, "url": watch_url, "video_id": video_id})

        if found_old:
            break

        # Scroll down to load more rows
        prev_count = count
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        new_count = await rows_locator.count()
        if new_count == prev_count:
            break

    return videos


async def _check_8k_in_player(page) -> bool:
    await page.wait_for_selector("#movie_player", timeout=30_000)
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
    """Check all private videos from the last 2 months for 8K availability."""
    result: Dict[str, Any] = {"videos": [], "status": "unknown", "error": None}
    cutoff = datetime.now() - timedelta(days=60)

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
            private_videos = await _collect_private_videos(page, cutoff)

            if not private_videos:
                result["status"] = "no_private_videos"
                return result

            for video_info in private_videos:
                entry: Dict[str, Any] = {
                    "title": video_info["title"],
                    "url": video_info["url"],
                    "has_8k": False,
                    "error": None,
                }
                watch_page = None
                try:
                    watch_page = await context.new_page()
                    await watch_page.goto(
                        video_info["url"], wait_until="networkidle"
                    )
                    entry["has_8k"] = await _check_8k_in_player(watch_page)
                except PlaywrightTimeoutError as exc:
                    entry["error"] = str(exc)
                    logger.warning("Timeout checking %s: %s", video_info["url"], exc)
                except Exception as exc:  # noqa: BLE001
                    entry["error"] = str(exc)
                    logger.warning("Error checking %s: %s", video_info["url"], exc)
                finally:
                    if watch_page:
                        await watch_page.close()

                result["videos"].append(entry)

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
