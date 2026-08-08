"""
rag/curator.py — relevance/quality filter pass between rerank and
sufficiency check.

Per docs/decisions.md D-010: pattern extracted from
guy-hartstein/company-research-agent's curator step. Implemented here as
a heuristic filter, NOT an LLM call -- given decisions.md D-022's
accepted-but-real latency cost per model call, adding a curator LLM call
to every agentic run would be a meaningful additional cost for a job
regex/heuristics can mostly do: drop near-empty content, drop chunks
that are pure noise (e.g. a snippet that's just a URL or nav text), and
soft-penalize chunks whose content barely overlaps the query at all.
"""

from __future__ import annotations

from core.state import RetrievedChunk

_MIN_CONTENT_LENGTH = 30  # characters -- below this, a "chunk" is usually
# a broken scrape (nav text, empty snippet) not real content


def _is_low_quality(chunk: RetrievedChunk) -> bool:
    content = chunk.get("content", "").strip()
    if len(content) < _MIN_CONTENT_LENGTH:
        return True
    # A snippet that's mostly non-alphabetic (nav/boilerplate junk) --
    # cheap heuristic, not a real content classifier.
    alpha_chars = sum(1 for c in content if c.isalpha())
    if alpha_chars < len(content) * 0.4:
        return True
    return False


def _query_overlap_words(chunk: RetrievedChunk, query_words: set[str]) -> int:
    content_words = set(chunk.get("content", "").lower().split())
    return len(content_words & query_words)


def curate(
    chunks: list[RetrievedChunk],
    query: str,
    min_overlap: int = 1,
) -> list[RetrievedChunk]:
    """Drops low-quality chunks and chunks with essentially zero lexical
    overlap with the query (a proxy for "this is probably off-topic
    noise that slipped past retrieval/rerank"). Does NOT re-rank --
    reranker.py already did that; this only removes, never reorders.
    """
    query_words = {w for w in query.lower().split() if len(w) > 2}  # skip tiny stopword-ish tokens

    curated: list[RetrievedChunk] = []
    for chunk in chunks:
        if _is_low_quality(chunk):
            continue
        if query_words and _query_overlap_words(chunk, query_words) < min_overlap:
            continue
        curated.append(chunk)

    return curated
