from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from alembic import command
from alembic.config import Config

from .config import get_settings
from .db import create_engine_and_session, create_schema
from .handlers import cards_router, payments_router, reports_router, start_router, transactions_router
from .services.reminders import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]


def _run_alembic_upgrade(database_url: str) -> None:
    config_path = BASE_DIR / "alembic.ini"
    alembic_cfg = Config(str(config_path))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")


async def _ensure_database_ready(database_url: str, engine) -> None:
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _run_alembic_upgrade, database_url)
        logger.info("Applied Alembic migrations successfully.")
    except Exception:
        logger.exception("Alembic migration failed, falling back to create_all.")
        await create_schema(engine)


async def main() -> None:
    settings = get_settings()

    engine, session_maker = create_engine_and_session(settings.database_url)
    await _ensure_database_ready(settings.database_url, engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(cards_router)
    dp.include_router(transactions_router)
    dp.include_router(reports_router)
    dp.include_router(payments_router)

    dp["settings"] = settings
    dp["session_maker"] = session_maker

    scheduler = setup_scheduler(bot, session_maker, settings)
    scheduler.start()

    logger.info("Bot started.")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
