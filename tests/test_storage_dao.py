from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.storage.dao import DaoConfig, StorageDao
from app.storage.db import DatabaseConfig, build_engine, build_session_factory, init_db


def test_save_news_item_idempotent(tmp_path: Path) -> None:
    engine = build_engine(DatabaseConfig(sqlite_path=tmp_path / "t.sqlite3"))
    init_db(engine)
    sf = build_session_factory(engine)
    dao = StorageDao(engine=engine, session_factory=sf, cfg=DaoConfig(ttl_days=30))

    item_id1 = dao.save_news_item(
        source_name="S",
        title="T",
        url="https://example.com/a?utm_source=x",
        canonical_url="https://example.com/a",
        title_hash="0" * 64,
        summary=None,
        published_at=datetime.now(tz=timezone.utc),
    )
    item_id2 = dao.save_news_item(
        source_name="S",
        title="T2",
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        title_hash="1" * 64,
        summary=None,
        published_at=None,
    )

    assert item_id1 is not None
    assert item_id2 is None

