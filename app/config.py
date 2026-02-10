import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:latest")
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
    run_timeout_sec: int = int(os.getenv("RUN_TIMEOUT_SEC", "300"))
    schedule_hour: int = int(os.getenv("SCHEDULE_HOUR", "6"))
    schedule_minute: int = int(os.getenv("SCHEDULE_MINUTE", "30"))
    schedule_tz: Optional[str] = os.getenv("SCHEDULE_TZ")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


settings = Settings()
