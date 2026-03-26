from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.llm.openrouter import OpenRouterClient
from app.llm.prompts import AnalysisBundle
from app.storage.dao import StorageDao

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalyzeConfig:
    batch_limit: int = 20
    concurrency: int = 4


async def analyze_unanalyzed_items(
    *,
    dao: StorageDao,
    llm: OpenRouterClient,
    cfg: AnalyzeConfig,
    only_item_ids: tuple[int, ...] | None = None,
) -> int:
    items = dao.get_unanalyzed_items(limit=cfg.batch_limit, only_item_ids=only_item_ids)
    if not items:
        return 0

    sem = asyncio.Semaphore(cfg.concurrency)

    async def analyze_one(item_id: int, title: str, url: str, summary: str | None) -> None:
        async with sem:
            bundle: AnalysisBundle = await llm.analyze_news_item(title=title, url=url, summary=summary)
            dao.save_analysis(
                item_id=item_id,
                model=llm.model,
                prompt_version=llm.prompt_version,
                payload=bundle.model_dump(),
            )

    await asyncio.gather(*(analyze_one(it.id, it.title, it.url, it.summary) for it in items))

    analyzed = len(items)
    logger.info("analysis_done", extra={"count": analyzed})
    return analyzed

