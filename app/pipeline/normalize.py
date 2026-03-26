from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.sources.models import NewsItem


@dataclass(frozen=True, slots=True)
class NormalizedItem:
    source_name: str
    title: str
    title_norm: str
    url: str
    canonical_url: str
    title_hash: str
    summary: str | None
    published_at: datetime | None


_WS_RE = re.compile(r"\s+")


def normalize_news_item(item: NewsItem) -> NormalizedItem:
    title = item.title.strip()
    title_norm = _normalize_title(title)
    canonical_url = canonicalize_url(item.url)
    title_hash = sha256_hex(title_norm)
    summary = item.summary.strip() if isinstance(item.summary, str) and item.summary.strip() else None

    return NormalizedItem(
        source_name=item.source_name,
        title=title,
        title_norm=title_norm,
        url=item.url.strip(),
        canonical_url=canonical_url,
        title_hash=title_hash,
        summary=summary,
        published_at=item.published_at,
    )


def _normalize_title(title: str) -> str:
    t = title.lower()
    t = _WS_RE.sub(" ", t).strip()
    return t


def canonicalize_url(url: str) -> str:
    """
    Canonicalize URL for dedupe.

    Minimal-but-safe version:
    - strip
    - drop fragments
    - drop common tracking query params
    - normalize scheme/host casing
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    u = url.strip()
    parts = urlsplit(u)
    query = parse_qsl(parts.query, keep_blank_values=True)

    drop = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}
    kept = [(k, v) for (k, v) in query if k.lower() not in drop]
    kept.sort(key=lambda kv: kv[0])

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            urlencode(kept, doseq=True),
            "",
        )
    )


def sha256_hex(text: str) -> str:
    import hashlib

    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()

