from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.llm.prompts import AnalysisBundle, ExtractionResult, PostGenerationResult, SynthesisResult
from app.pipeline.analyze import AnalyzeConfig, analyze_unanalyzed_items
from app.storage.dao import DaoConfig, StorageDao
from app.storage.db import DatabaseConfig, build_engine, build_session_factory, init_db


@dataclass(frozen=True)
class FakeLlm:
    model: str = "fake-model"
    prompt_version: str = "fake-v"
    delay_s: float = 0.05

    async def analyze_news_item(self, *, title: str, url: str, summary: str | None) -> AnalysisBundle:
        await asyncio.sleep(self.delay_s)
        return AnalysisBundle(
            extraction=ExtractionResult(facts=[title], key_signals=["sig"]),
            synthesis=SynthesisResult(why_now="now", business_angles=["angle"]),
            post=PostGenerationResult(
                headline="h",
                hook="k",
                bullet_points=["b1", "b2", "b3"],
                what_to_do=["a1"],
                why_now="w",
                sources=[url],
            ),
        )


@pytest.mark.asyncio
async def test_analyze_pipeline_saves_all(tmp_path: Path) -> None:
    engine = build_engine(DatabaseConfig(sqlite_path=tmp_path / "t.sqlite3"))
    init_db(engine)
    sf = build_session_factory(engine)
    dao = StorageDao(engine=engine, session_factory=sf, cfg=DaoConfig(ttl_days=30))

    ids: list[int] = []
    for i in range(5):
        item_id = dao.save_news_item(
            source_name="S",
            title=f"T{i}",
            url=f"https://example.com/{i}",
            canonical_url=f"https://example.com/{i}",
            title_hash=f"{i}".zfill(64),
            summary=None,
            published_at=datetime.now(tz=timezone.utc),
        )
        assert item_id is not None
        ids.append(item_id)

    llm = FakeLlm()
    n = await analyze_unanalyzed_items(dao=dao, llm=llm, cfg=AnalyzeConfig(batch_limit=10, concurrency=3))
    assert n == 5

    remaining = dao.get_unanalyzed_items(limit=10)
    assert remaining == ()

