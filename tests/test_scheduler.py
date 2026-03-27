from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.scheduler import CycleConfig, run_cycle
from app.sources.base import SourceFetchResult
from app.sources.loader import SourcesConfig
from app.sources.models import NewsItem
from app.storage.dao import DaoConfig, StorageDao
from app.storage.db import DatabaseConfig, build_engine, build_session_factory, init_db


class FakeSource:
    name = "fake"

    async def fetch(self) -> SourceFetchResult:
        item = NewsItem(
            source_name="fake",
            title="AI startup raises funding",
            url="https://example.com/news-1",
            summary="summary",
            published_at=datetime.now(tz=timezone.utc),
        )
        return SourceFetchResult(items=(item,))


class FakePublisher:
    def __init__(self) -> None:
        self.called = False

    async def send_digest_post(self, *, dao: StorageDao, post) -> bool:  # type: ignore[no-untyped-def]
        self.called = True
        return True


class FakeLlm:
    model = "fake"
    prompt_version = "fake"

    async def analyze_news_item(self, *, title: str, url: str, summary: str | None):  # type: ignore[no-untyped-def]
        from app.llm.prompts import AnalysisBundle, ExtractionResult, PostGenerationResult, SynthesisResult

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


def _dao(tmp_path: Path) -> StorageDao:
    engine = build_engine(DatabaseConfig(sqlite_path=tmp_path / "t.sqlite3"))
    init_db(engine)
    sf = build_session_factory(engine)
    return StorageDao(engine=engine, session_factory=sf, cfg=DaoConfig(ttl_days=30))


@pytest.mark.asyncio
async def test_run_cycle_dry_run_skips_publish_and_analyze(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dao = _dao(tmp_path)
    publisher = FakePublisher()

    monkeypatch.setattr(
        "app.scheduler.load_sources_from_yaml",
        lambda path: SourcesConfig(rss=(FakeSource(),), api=()),
    )

    await run_cycle(
        dao=dao,
        cfg=CycleConfig(sources_config_path="sources.yaml", dry_run=True),
        llm=None,
        publisher=publisher,
    )
    assert publisher.called is False
    assert len(dao.get_unanalyzed_items(limit=10)) == 1


@pytest.mark.asyncio
async def test_run_cycle_live_analyzes_and_publishes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dao = _dao(tmp_path)
    publisher = FakePublisher()

    monkeypatch.setattr(
        "app.scheduler.load_sources_from_yaml",
        lambda path: SourcesConfig(rss=(FakeSource(),), api=()),
    )

    await run_cycle(
        dao=dao,
        cfg=CycleConfig(sources_config_path="sources.yaml", dry_run=False),
        llm=FakeLlm(),
        publisher=publisher,
    )
    assert publisher.called is True
    assert dao.get_unanalyzed_items(limit=10) == ()
