import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)

def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    studio_url: str = os.getenv(
        "YOUTUBE_STUDIO_URL",
        "https://studio.youtube.com/channel/UC8eBNgDl6v5cW7wgwcCekTg",
    )
    user_data_dir: str = os.getenv(
        "YOUTUBE_USER_DATA_DIR",
        os.path.join(os.getcwd(), ".playwright-profile"),
    )
    headless: bool = _get_bool("HEADLESS", False)
    slow_mo_ms: int = int(os.getenv("SLOW_MO_MS", "50"))
    browser_user_agent: str = os.getenv(
        "BROWSER_USER_AGENT", _DEFAULT_BROWSER_USER_AGENT
    )
    browser_navigation_timeout_ms: int = int(
        os.getenv("BROWSER_NAVIGATION_TIMEOUT_MS", "45000")
    )
    browser_action_timeout_ms: int = int(
        os.getenv("BROWSER_ACTION_TIMEOUT_MS", "30000")
    )
    run_timeout_sec: int = int(os.getenv("RUN_TIMEOUT_SEC", "300"))
    schedule_hour: int = int(os.getenv("SCHEDULE_HOUR", "6"))
    schedule_minute: int = int(os.getenv("SCHEDULE_MINUTE", "30"))
    schedule_tz: Optional[str] = os.getenv("SCHEDULE_TZ")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


settings = Settings()
