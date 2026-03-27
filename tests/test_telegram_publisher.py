from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline.compose import PreparedPost
from app.storage.dao import DaoConfig, StorageDao
from app.storage.db import DatabaseConfig, build_engine, build_session_factory, init_db
from app.telegram.publisher import TelegramPublisher


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    async def __aenter__(self) -> "FakeBot":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def send_message(self, *, chat_id: str, text: str) -> None:
        assert chat_id == "@test_channel"
        self.sent_messages.append(text)


@pytest.mark.asyncio
async def test_send_digest_post_splits_and_saves_post(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = build_engine(DatabaseConfig(sqlite_path=tmp_path / "t.sqlite3"))
    init_db(engine)
    sf = build_session_factory(engine)
    dao = StorageDao(engine=engine, session_factory=sf, cfg=DaoConfig(ttl_days=30))

    fake_bot = FakeBot()
    monkeypatch.setattr("app.telegram.publisher.Bot", lambda token: fake_bot)

    publisher = TelegramPublisher(bot_token="token", channel_id="@test_channel", send_delay_s=0, max_message_len=120)
    post = PreparedPost(
        kind="digest",
        item_ids=(1, 2),
        messages=("🚀 " + ("очень длинная строка " * 30),),
    )

    sent = await publisher.send_digest_post(dao=dao, post=post)
    assert sent is True
    assert len(fake_bot.sent_messages) >= 2
    assert all(len(chunk) <= 120 for chunk in fake_bot.sent_messages)

    existing = dao.find_existing_post(
        kind="digest",
        channel_id="@test_channel",
        content=publisher._render_post(post),
        item_ids=(1, 2),
    )
    assert existing is not None


@pytest.mark.asyncio
async def test_send_digest_post_idempotent_skip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine = build_engine(DatabaseConfig(sqlite_path=tmp_path / "t.sqlite3"))
    init_db(engine)
    sf = build_session_factory(engine)
    dao = StorageDao(engine=engine, session_factory=sf, cfg=DaoConfig(ttl_days=30))

    fake_bot = FakeBot()
    monkeypatch.setattr("app.telegram.publisher.Bot", lambda token: fake_bot)

    publisher = TelegramPublisher(bot_token="token", channel_id="@test_channel", send_delay_s=0)
    post = PreparedPost(kind="digest", item_ids=(1,), messages=("test message",))

    first = await publisher.send_digest_post(dao=dao, post=post)
    second = await publisher.send_digest_post(dao=dao, post=post)
    assert first is True
    assert second is False
