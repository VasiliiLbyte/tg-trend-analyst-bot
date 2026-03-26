from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.pipeline.normalize import NormalizedItem
from app.storage.dao import StorageDao
from app.storage.models import Item

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DedupeConfig:
    recent_window_days: int = 30
    title_similarity_threshold: float = 0.82


def filter_new_items(
    items: tuple[NormalizedItem, ...],
    *,
    dao: StorageDao,
    cfg: DedupeConfig,
) -> tuple[NormalizedItem, ...]:
    since = datetime.now(tz=timezone.utc) - timedelta(days=cfg.recent_window_days)
    recent = dao.get_recent_items(since=since)
    recent_by_hash = _index_by_title_hash(recent)

    kept: list[NormalizedItem] = []
    for it in items:
        if _is_duplicate(it, recent, recent_by_hash, cfg):
            continue
        kept.append(it)

    logger.info(
        "dedupe_done",
        extra={"in_count": len(items), "out_count": len(kept), "recent_count": len(recent)},
    )
    return tuple(kept)


def _index_by_title_hash(items: tuple[Item, ...]) -> dict[str, list[Item]]:
    out: dict[str, list[Item]] = {}
    for it in items:
        out.setdefault(it.title_hash, []).append(it)
    return out


def _is_duplicate(
    it: NormalizedItem,
    recent: tuple[Item, ...],
    recent_by_hash: dict[str, list[Item]],
    cfg: DedupeConfig,
) -> bool:
    # Fast path: exact canonical URL already exists (enforced by DB too, but cheaper to skip work early)
    for r in recent:
        if r.canonical_url == it.canonical_url:
            return True

    # Fast path: exact normalized title hash match
    if it.title_hash in recent_by_hash:
        return True

    # Fuzzy title similarity against recent items (token overlap)
    tokens_a = _title_tokens(it.title_norm)
    if not tokens_a:
        return False

    for r in recent:
        b_norm = _normalize_title(r.title)
        tokens_b = _title_tokens(b_norm)
        sim = jaccard_similarity(tokens_a, tokens_b)
        if sim >= cfg.title_similarity_threshold:
            return True

    return False


_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


def _normalize_title(title: str) -> str:
    t = title.lower()
    t = _WS_RE.sub(" ", t).strip()
    return t


def _title_tokens(title_norm: str) -> frozenset[str]:
    return frozenset(m.group(0).lower() for m in _TOKEN_RE.finditer(title_norm))


def jaccard_similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union

