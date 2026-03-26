from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.sources.base import BaseSource
from app.sources.rss import RssSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourcesConfig:
    rss: tuple[RssSource, ...]
    api: tuple[BaseSource, ...]


def load_sources_from_yaml(path: Path) -> SourcesConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    rss_cfg = raw.get("rss", []) or []
    rss_sources: list[RssSource] = []
    for s in rss_cfg:
        name = (s.get("name") or "").strip()
        url = (s.get("url") or "").strip()
        if not name or not url:
            continue
        rss_sources.append(RssSource(name=name, url=url))

    api_sources: list[BaseSource] = []
    logger.info(
        "sources_loaded",
        extra={"rss": len(rss_sources), "api": len(api_sources), "path": str(path)},
    )
    return SourcesConfig(rss=tuple(rss_sources), api=tuple(api_sources))

