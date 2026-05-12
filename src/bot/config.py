from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    timezone: str = "Asia/Kolkata"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cardbot",
    ).strip()
    timezone = os.getenv("TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Please configure it in your .env file.")

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        timezone=timezone,
    )
