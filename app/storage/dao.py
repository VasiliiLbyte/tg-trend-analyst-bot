from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.sources.models import NewsItem
from app.storage.models import Analysis, Item

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DaoConfig:
    ttl_days: int = 30


class StorageDao:
    def __init__(self, *, engine: Engine, session_factory: sessionmaker[Session], cfg: DaoConfig) -> None:
        self._engine = engine
        self._sf = session_factory
        self._cfg = cfg

    def save_news_item(
        self,
        *,
        source_name: str,
        title: str,
        url: str,
        canonical_url: str,
        title_hash: str,
        summary: str | None,
        published_at: datetime | None,
    ) -> int | None:
        """
        Insert-only with uniqueness on canonical_url.

        Returns the new item id, or None if it already exists.
        """
        with self._sf() as session:
            existing = session.execute(select(Item.id).where(Item.canonical_url == canonical_url)).scalar_one_or_none()
            if existing is not None:
                return None

            item = Item(
                source_name=source_name,
                title=title,
                url=url,
                canonical_url=canonical_url,
                title_hash=title_hash,
                summary=summary,
                published_at=published_at,
            )
            session.add(item)
            session.commit()
            return item.id

    def get_recent_items(self, *, since: datetime) -> tuple[Item, ...]:
        with self._sf() as session:
            rows = session.execute(select(Item).where(Item.created_at >= since)).scalars().all()
            return tuple(rows)

    def get_unanalyzed_items(self, *, limit: int = 50, only_item_ids: tuple[int, ...] | None = None) -> tuple[Item, ...]:
        with self._sf() as session:
            q = select(Item).where(Item.analyzed_at.is_(None))
            if only_item_ids:
                q = q.where(Item.id.in_(only_item_ids))
            rows = (
                session.execute(
                    q.order_by(Item.created_at.desc()).limit(limit)
                )
                .scalars()
                .all()
            )
            return tuple(rows)

    def mark_as_analyzed(self, *, item_id: int, analyzed_at: datetime | None = None) -> None:
        ts = analyzed_at or datetime.now(tz=timezone.utc)
        with self._sf() as session:
            session.execute(update(Item).where(Item.id == item_id).values(analyzed_at=ts))
            session.commit()

    def mark_as_posted(self, *, item_id: int, posted_at: datetime | None = None) -> None:
        ts = posted_at or datetime.now(tz=timezone.utc)
        with self._sf() as session:
            session.execute(update(Item).where(Item.id == item_id).values(posted_at=ts))
            session.commit()

    def save_analysis(
        self,
        *,
        item_id: int,
        model: str,
        prompt_version: str,
        payload: dict[str, object],
        analyzed_at: datetime | None = None,
    ) -> None:
        ts = analyzed_at or datetime.now(tz=timezone.utc)
        with self._sf() as session:
            analysis = Analysis(item_id=item_id, model=model, prompt_version=prompt_version, payload=payload)
            session.add(analysis)
            session.execute(update(Item).where(Item.id == item_id).values(analyzed_at=ts))
            session.commit()

    def cleanup_old_items(self) -> int:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=self._cfg.ttl_days)
        with self._sf() as session:
            res = session.execute(delete(Item).where(Item.created_at < cutoff))
            session.commit()
            deleted = int(res.rowcount or 0)
            logger.info("cleanup_old_items", extra={"deleted": deleted, "cutoff": cutoff.isoformat()})
            return deleted


def news_item_to_fields(item: NewsItem, *, canonical_url: str, title_hash: str) -> dict[str, object]:
    return {
        "source_name": item.source_name,
        "title": item.title,
        "url": item.url,
        "canonical_url": canonical_url,
        "title_hash": title_hash,
        "summary": item.summary,
        "published_at": item.published_at,
    }

