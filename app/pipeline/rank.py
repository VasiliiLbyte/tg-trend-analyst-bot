from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.normalize import NormalizedItem


@dataclass(frozen=True, slots=True)
class RankedItem:
    item: NormalizedItem
    category: str  # "business_trend" | "tech_breakthrough" | "other"
    score: float


_TECH_KW = {
    "ai",
    "ml",
    "model",
    "llm",
    "chip",
    "gpu",
    "quantum",
    "breakthrough",
    "research",
    "paper",
    "benchmark",
    "open-source",
    "robot",
    "robotics",
    "fusion",
}
_BIZ_KW = {
    "startup",
    "funding",
    "ipo",
    "revenue",
    "market",
    "pricing",
    "enterprise",
    "regulation",
    "tariff",
    "deal",
    "acquisition",
    "merger",
    "supply",
    "chain",
}

_WORD_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


def classify_and_score(item: NormalizedItem) -> RankedItem:
    text = f"{item.title_norm} {(item.summary or '').lower()}"
    words = {m.group(0).lower() for m in _WORD_RE.finditer(text)}

    tech_hits = len(words & _TECH_KW)
    biz_hits = len(words & _BIZ_KW)

    if tech_hits > biz_hits and tech_hits > 0:
        category = "tech_breakthrough"
    elif biz_hits > 0:
        category = "business_trend"
    else:
        category = "other"

    score = float(tech_hits + biz_hits)
    if category in {"tech_breakthrough", "business_trend"}:
        score += 1.0
    if item.published_at is not None:
        score += 0.1

    return RankedItem(item=item, category=category, score=score)


def rank_items(items: tuple[NormalizedItem, ...]) -> tuple[RankedItem, ...]:
    ranked = [classify_and_score(it) for it in items]
    ranked.sort(key=lambda r: r.score, reverse=True)
    return tuple(ranked)

