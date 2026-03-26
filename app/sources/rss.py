from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.sources.base import SourceFetchResult
from app.sources.models import NewsItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RssSource:
    name: str
    url: str
    timeout_s: float = 20.0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=1, max=8))
    async def _get(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True) as client:
            r = await client.get(self.url, headers={"User-Agent": "tg-trend-analyst-bot/1.0"})
            r.raise_for_status()
            return r.text

    async def fetch(self) -> SourceFetchResult:
        try:
            raw = await self._get()
        except httpx.HTTPError as e:
            logger.warning("rss_fetch_failed", extra={"source": self.name, "url": self.url, "err": str(e)})
            return SourceFetchResult(items=())

        parsed = feedparser.parse(raw)
        if getattr(parsed, "bozo", 0):
            exc = getattr(parsed, "bozo_exception", None)
            logger.warning(
                "rss_parse_bozo",
                extra={"source": self.name, "url": self.url, "err": str(exc) if exc else None},
            )

        items: list[NewsItem] = []
        for entry in getattr(parsed, "entries", []) or []:
            title = (getattr(entry, "title", None) or "").strip()
            link = (getattr(entry, "link", None) or "").strip()
            if not title or not link:
                continue

            summary = getattr(entry, "summary", None)
            published_at = _parse_datetime(entry)
            items.append(
                NewsItem(
                    source_name=self.name,
                    title=title,
                    url=link,
                    summary=summary.strip() if isinstance(summary, str) else None,
                    published_at=published_at,
                )
            )

        logger.info("rss_fetch_ok", extra={"source": self.name, "count": len(items)})
        return SourceFetchResult(items=tuple(items))


def _parse_datetime(entry: object) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        v = getattr(entry, attr, None)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None

