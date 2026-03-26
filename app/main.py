from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import load_settings
from app.llm.openrouter import OpenRouterClient, OpenRouterConfig
from app.logging import LoggingConfig, configure_logging
from app.scheduler import CycleConfig, SchedulerConfig, build_scheduler, run_cycle
from app.storage.dao import DaoConfig, StorageDao
from app.storage.db import DatabaseConfig, build_engine, build_session_factory, init_db
from app.telegram.publisher import TelegramPublisher

logger = logging.getLogger(__name__)

_MISSING = "__MISSING__"


async def _run() -> None:
    settings = load_settings()
    configure_logging(LoggingConfig(level=settings.log_level))

    logger.info("app_start", extra={"env": settings.app_env, "tz": settings.tz})

    engine = build_engine(DatabaseConfig(sqlite_path=settings.sqlite_path))
    init_db(engine)
    session_factory = build_session_factory(engine)
    dao = StorageDao(engine=engine, session_factory=session_factory, cfg=DaoConfig(ttl_days=30))

    publisher: TelegramPublisher | None = None
    llm: OpenRouterClient | None = None

    if settings.bot_token != _MISSING and settings.channel_id != _MISSING:
        publisher = TelegramPublisher(bot_token=settings.bot_token, channel_id=settings.channel_id)

    if settings.openrouter_api_key != _MISSING:
        llm = OpenRouterClient(
            cfg=OpenRouterConfig(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
            )
        )

    scheduler = build_scheduler(
        SchedulerConfig(tz=settings.tz, every_hours=settings.schedule_every_hours),
        job=lambda: run_cycle(
            dao=dao,
            cfg=CycleConfig(
                sources_config_path=str(settings.sources_config_path),
                ttl_days=30,
                dry_run=settings.dry_run,
            ),
            llm=llm,
            publisher=publisher,
        ),
    )
    # Run one cycle immediately on startup (useful for local development)
    await run_cycle(
        dao=dao,
        cfg=CycleConfig(
            sources_config_path=str(settings.sources_config_path),
            ttl_days=30,
            dry_run=settings.dry_run,
        ),
        llm=llm,
        publisher=publisher,
    )

    scheduler.start()

    # Keep process alive. If BOT_TOKEN isn't configured yet, don't start polling.
    if settings.bot_token == _MISSING:
        logger.info("bot_token_missing_skip_polling")
        await asyncio.Event().wait()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

