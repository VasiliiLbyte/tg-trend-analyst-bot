from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.sources.models import NewsItem


@dataclass(frozen=True)
class SourceFetchResult:
    items: tuple[NewsItem, ...]


class BaseSource(Protocol):
    name: str

    async def fetch(self) -> SourceFetchResult: ...

