from __future__ import annotations

import asyncio
import argparse
import logging
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    dry_run_override: bool | None
    scheduler_only_override: bool | None
    run_once: bool


def parse_args() -> RuntimeOptions:
    parser = argparse.ArgumentParser(description="tg-trend-analyst-bot runner")
    parser.add_argument("--dry-run", action="store_true", help="Run cycle without Telegram publishing.")
    parser.add_argument(
        "--scheduler-only",
        action="store_true",
        help="Run only scheduler, skip aiogram polling.",
    )
    parser.add_argument("--once", action="store_true", help="Run exactly one cycle and exit.")
    args = parser.parse_args()
    return RuntimeOptions(
        dry_run_override=True if args.dry_run else None,
        scheduler_only_override=True if args.scheduler_only else None,
        run_once=bool(args.once),
    )


async def _run(opts: RuntimeOptions) -> None:
    settings = load_settings()
    configure_logging(LoggingConfig(level=settings.log_level))

    dry_run = opts.dry_run_override if opts.dry_run_override is not None else settings.dry_run
    scheduler_only = (
        opts.scheduler_only_override if opts.scheduler_only_override is not None else settings.scheduler_only
    )

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

    cycle_cfg = CycleConfig(sources_config_path=str(settings.sources_config_path), ttl_days=30, dry_run=dry_run)

    async def cycle_job() -> None:
        await run_cycle(dao=dao, cfg=cycle_cfg, llm=llm, publisher=publisher)

    scheduler = build_scheduler(
        SchedulerConfig(tz=settings.tz, every_hours=settings.schedule_every_hours),
        job=cycle_job,
    )

    if opts.run_once:
        await cycle_job()
        logger.info("run_once_finished")
        return

    if settings.first_run_immediately:
        await cycle_job()

    scheduler.start()

    # Keep process alive. Skip polling in scheduler-only mode or without bot token.
    if scheduler_only or settings.bot_token == _MISSING:
        logger.info(
            "scheduler_only_mode",
            extra={"scheduler_only": scheduler_only, "bot_token_configured": settings.bot_token != _MISSING},
        )
        await asyncio.Event().wait()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()

