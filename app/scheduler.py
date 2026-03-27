from __future__ import annotations

import logging
from dataclasses import replace
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.pipeline.dedupe import DedupeConfig, filter_new_items
from app.pipeline.normalize import normalize_news_item
from app.pipeline.rank import rank_items
from app.pipeline.compose import compose_digest
from app.pipeline.analyze import AnalyzeConfig, analyze_unanalyzed_items
from app.llm.openrouter import OpenRouterClient
from app.telegram.publisher import TelegramPublisher
from app.sources.loader import load_sources_from_yaml
from app.storage.dao import StorageDao

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerConfig:
    tz: str
    every_hours: int


def build_scheduler(
    cfg: SchedulerConfig,
    job: Callable[[], Awaitable[None]],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=cfg.tz)
    scheduler.add_job(
        job,
        trigger=IntervalTrigger(hours=cfg.every_hours),
        id="run_cycle",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60 * 30,
    )
    return scheduler


@dataclass(frozen=True)
class CycleConfig:
    sources_config_path: str
    dry_run: bool
    ttl_days: int = 30
    top_k: int = 7


async def run_cycle(
    *,
    dao: StorageDao,
    cfg: CycleConfig,
    llm: OpenRouterClient | None = None,
    publisher: TelegramPublisher | None = None,
) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    logger.info("cycle_start ts=%s", now)

    sources = load_sources_from_yaml(path=Path(cfg.sources_config_path))
    rss_sources = sources.rss

    fetched: list = []
    for src in rss_sources:
        res = await src.fetch()
        fetched.extend(res.items)

    normalized = tuple(normalize_news_item(it) for it in fetched)
    deduped = filter_new_items(normalized, dao=dao, cfg=DedupeConfig(recent_window_days=cfg.ttl_days))
    ranked = rank_items(deduped)

    inserted_ids: list[int] = []
    inserted_id_by_canonical_url: dict[str, int] = {}
    for r in ranked:
        new_id = dao.save_news_item(
            source_name=r.item.source_name,
            title=r.item.title,
            url=r.item.url,
            canonical_url=r.item.canonical_url,
            title_hash=r.item.title_hash,
            summary=r.item.summary,
            published_at=r.item.published_at,
        )
        if new_id is not None:
            inserted_ids.append(new_id)
            inserted_id_by_canonical_url[r.item.canonical_url] = new_id

    analyzed_count = 0
    if not cfg.dry_run:
        if llm is None:
            raise RuntimeError("llm_required_when_not_dry_run")
        analyzed_count = await analyze_unanalyzed_items(
            dao=dao,
            llm=llm,
            cfg=AnalyzeConfig(batch_limit=20, concurrency=4),
            only_item_ids=tuple(inserted_ids),
        )

    prepared = compose_digest(ranked=ranked, top_k=cfg.top_k)
    top_ranked = ranked[: cfg.top_k]
    top_item_ids = tuple(
        inserted_id_by_canonical_url[r.item.canonical_url]
        for r in top_ranked
        if r.item.canonical_url in inserted_id_by_canonical_url
    )
    prepared = replace(prepared, item_ids=top_item_ids)
    logger.info(
        "prepare_for_publish dry_run=%s kind=%s messages=%d item_ids=%d",
        cfg.dry_run,
        prepared.kind,
        len(prepared.messages),
        len(prepared.item_ids),
    )

    published = False
    if cfg.dry_run:
        preview = prepared.messages[0] if prepared.messages else ""
        logger.info("dry_run_skip_publish full_preview_first_message:\n%s", preview)
    else:
        if publisher is None:
            raise RuntimeError("publisher_required_when_not_dry_run")
        published = await publisher.send_digest_post(dao=dao, post=prepared)

    dao.cleanup_old_items()
    logger.info(
        "cycle_end ts=%s fetched=%d normalized=%d deduped=%d inserted=%d analyzed=%d published=%s",
        now,
        len(fetched),
        len(normalized),
        len(deduped),
        len(inserted_ids),
        analyzed_count,
        published,
    )

