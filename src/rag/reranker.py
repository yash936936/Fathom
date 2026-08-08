"""
rag/reranker.py — reranks fused retrieval results.

Per docs/decisions.md D-019: trd.md §4 names a cross-encoder reranker as
the v1 target. That's a real ML model (sentence-transformers-class
dependency, i.e. torch) -- directly conflicts with trd.md §1's CPU-only/
<6GB constraint the same way a dense embedding model would (see D-019).
v1 ships a heuristic reranker instead: BM25 score (where available, from
tools/vector_store.py) combined with a recency boost (favoring dated
results when requires_recency is set), not a learned relevance model.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.state import RetrievedChunk

# How much a recent result's score is boosted relative to an undated one.
# Deliberately a simple multiplier, not a decay curve -- v1 heuristic,
# see module docstring. Revisit if Phase 6 eval data shows recency
# handling is a weak point worth investing more in.
_RECENCY_BOOST = 1.5
_RECENCY_WINDOW_DAYS = 30


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    # Tools normalize dates loosely (ISO date, RFC 822 pubDate substrings,
    # etc.) -- try a couple of common shapes rather than assuming one.
    for fmt in ("%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(date_str[:len(fmt) + 5], fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _score(chunk: RetrievedChunk, requires_recency: bool) -> float:
    base = chunk.get("relevance_score") or 0.0
    # Undated web results start at a small positive floor rather than 0,
    # so a highly relevant but undated result isn't automatically ranked
    # below a barely-relevant dated one.
    if base == 0.0:
        base = 0.1

    if not requires_recency:
        return base

    parsed = _parse_date(chunk.get("date"))
    if parsed is None:
        return base

    age_days = (datetime.now(timezone.utc) - parsed).days
    if age_days <= _RECENCY_WINDOW_DAYS:
        return base * _RECENCY_BOOST
    return base


def rerank(
    chunks: list[RetrievedChunk],
    top_k: int = 8,
    requires_recency: bool = False,
) -> list[RetrievedChunk]:
    scored = sorted(chunks, key=lambda c: _score(c, requires_recency), reverse=True)
    return scored[:top_k]
