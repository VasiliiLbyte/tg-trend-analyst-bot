from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import load_settings
from app.logging import LoggingConfig, configure_logging
from app.scheduler import CycleConfig, SchedulerConfig, build_scheduler, run_cycle
from app.storage.dao import DaoConfig, StorageDao
from app.storage.db import DatabaseConfig, build_engine, build_session_factory, init_db

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = load_settings()
    configure_logging(LoggingConfig(level=settings.log_level))

    logger.info("app_start", extra={"env": settings.app_env, "tz": settings.tz})

    engine = build_engine(DatabaseConfig(sqlite_path=settings.sqlite_path))
    init_db(engine)
    session_factory = build_session_factory(engine)
    dao = StorageDao(engine=engine, session_factory=session_factory, cfg=DaoConfig(ttl_days=30))

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    scheduler = build_scheduler(
        SchedulerConfig(tz=settings.tz, every_hours=settings.schedule_every_hours),
        job=lambda: run_cycle(
            dao=dao,
            cfg=CycleConfig(sources_config_path=str(settings.sources_config_path), ttl_days=30),
        ),
    )
    scheduler.start()

    # Polling keeps the event loop alive; later we'll add handlers and a real cycle job.
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

