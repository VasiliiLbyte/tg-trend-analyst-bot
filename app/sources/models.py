from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    source_name: str
    title: str
    url: str
    summary: str | None
    published_at: datetime | None

