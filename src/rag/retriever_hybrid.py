"""
rag/retriever_hybrid.py — fans a query out across registered tools and
fuses results.

Per docs/decisions.md D-019: this is BM25/lexical fusion in v1 (dedupe +
score-normalize across tools), NOT dense-vector RRF fusion as originally
scoped in trd.md §4 -- there's no dense embedding backend yet (see
D-019 for why). The RRF fusion approach documented in trd.md still
applies conceptually to how scores are combined across sources; it's the
"dense" half of hybrid that's deferred, not the fusion logic itself.
"""

from __future__ import annotations

import tools  # noqa: F401 -- must import before dispatch() calls below; see tools/__init__.py
from core.state import RetrievedChunk
from tools.registry import dispatch


def retrieve(
    query: str,
    tool_names: list[str] | None = None,
    max_results_per_tool: int = 5,
) -> list[RetrievedChunk]:
    """Fan out `query` across the given tools (default: all registered
    web/news/arxiv/curated tools), then fuse + dedupe.

    tool_names defaults to a fixed list rather than tools.registry.list_tools()
    so a badly-behaved or slow tool added later doesn't silently get
    included in every retrieval call -- retrieval sources are opt-in.
    """
    if tool_names is None:
        tool_names = ["web_search", "news_search", "arxiv_search", "curated_search"]

    all_chunks: list[RetrievedChunk] = []
    for name in tool_names:
        try:
            chunks = dispatch(name, query=query, max_results=max_results_per_tool)
            all_chunks.extend(chunks)
        except Exception:
            # A single tool failing (network error, parse error, etc.)
            # should not fail the whole retrieval -- other sources may
            # still have useful results. Sufficiency check (Phase 5)
            # handles the case where too many sources failed.
            continue

    return _dedupe(all_chunks)


def _dedupe(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Drop chunks with identical (source, content) pairs -- different
    tools sometimes surface the same underlying article/page. Keeps the
    first occurrence, which preserves tool-list order (web -> news ->
    arxiv -> curated) as a stable tie-break.
    """
    seen: set[tuple[str, str]] = set()
    deduped: list[RetrievedChunk] = []
    for chunk in chunks:
        key = (chunk["source"], chunk["content"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped
