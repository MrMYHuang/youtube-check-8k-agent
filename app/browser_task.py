import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from playwright.async_api import (
    Page,
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from .config import settings

logger = logging.getLogger(__name__)

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_VIDEOS_PAGE_SUFFIX = "/videos"

_UNSUPPORTED_BROWSER_TEXT = "unsupported browser"


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


def _videos_page_url(studio_url: str) -> str:
    base_url = studio_url.rstrip("/")
    if base_url.endswith(_VIDEOS_PAGE_SUFFIX):
        return base_url
    return f"{base_url}{_VIDEOS_PAGE_SUFFIX}"


async def _goto_with_retries(page: Page, url: str, attempts: int = 2) -> None:
    last_error: Optional[PlaywrightTimeoutError] = None
    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("load")
            return
        except PlaywrightTimeoutError as exc:
            last_error = exc
            logger.warning(
                "Navigation attempt %s/%s timed out for %s: %s",
                attempt,
                attempts,
                url,
                exc,
            )
            if attempt == attempts:
                raise
            await page.wait_for_timeout(1500)

    if last_error is not None:
        raise last_error


async def _wait_for_studio_rows(page: Page) -> None:
    rows_locator = page.locator("ytcp-video-row")
    unsupported_locator = page.locator(f"text={_UNSUPPORTED_BROWSER_TEXT}")
    sign_in_locator = page.locator("text=Sign in")

    deadline = asyncio.get_running_loop().time() + (
        settings.browser_action_timeout_ms / 1000
    )
    while asyncio.get_running_loop().time() < deadline:
        if await rows_locator.count() > 0:
            return

        if await unsupported_locator.count() > 0:
            raise RuntimeError(
                "YouTube Studio returned an unsupported browser page. "
                "Check the browser user agent or use a Chrome-based channel."
            )

        if await sign_in_locator.count() > 0:
            raise RuntimeError(
                "YouTube Studio redirected to sign-in. Refresh the saved session "
                "with HEADLESS=false and log in again."
            )

        await page.wait_for_timeout(500)

    raise PlaywrightTimeoutError(
        "Timed out waiting for YouTube Studio video rows to load"
    )


async def _ensure_videos_page(page: Page, studio_url: str) -> None:
    target_url = _videos_page_url(studio_url)
    await _goto_with_retries(page, target_url)

    if _VIDEOS_PAGE_SUFFIX not in page.url:
        await _goto_with_retries(page, target_url)

    await _wait_for_studio_rows(page)


async def _collect_private_videos(
    page: Page, cutoff: datetime
) -> List[Dict[str, Any]]:
    """Scroll through the video list and collect private videos within the cutoff."""
    videos: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    await _wait_for_studio_rows(page)
    rows_locator = page.locator("ytcp-video-row")

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


async def _check_8k_in_player(page: Page) -> bool:
    await page.wait_for_selector(
        "#movie_player", timeout=settings.browser_action_timeout_ms
    )
    await page.hover("#movie_player", timeout=10_000)
    await page.click("#movie_player", timeout=10_000)
    settings_btn = page.locator("button.ytp-settings-button")
    await settings_btn.wait_for(state="attached", timeout=10_000)
    await settings_btn.evaluate("button => button.click()")
    await page.wait_for_selector(".ytp-panel-menu", timeout=10_000)
    quality_item = (
        page.locator(".ytp-panel-menu .ytp-menuitem").filter(has_text="Quality").first
    )
    await quality_item.evaluate("item => item.click()")
    await page.wait_for_selector(".ytp-panel-menu", timeout=10_000)

    items = page.locator(".ytp-panel-menu .ytp-menuitem")
    for text in await items.all_inner_texts():
        normalized_text = text.strip()
        if "4320" in normalized_text or "8K" in normalized_text or "8k" in normalized_text:
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
            user_agent=settings.browser_user_agent,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context.set_default_timeout(settings.browser_action_timeout_ms)
        context.set_default_navigation_timeout(settings.browser_navigation_timeout_ms)
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
                    await _goto_with_retries(watch_page, video_info["url"])
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
