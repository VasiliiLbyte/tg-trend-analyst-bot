from __future__ import annotations

from app.pipeline.dedupe import jaccard_similarity


def test_jaccard_similarity_identical() -> None:
    a = frozenset({"a", "b", "c"})
    b = frozenset({"a", "b", "c"})
    assert jaccard_similarity(a, b) == 1.0


def test_jaccard_similarity_disjoint() -> None:
    a = frozenset({"a"})
    b = frozenset({"b"})
    assert jaccard_similarity(a, b) == 0.0

