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

from typing import Callable

import tools  # noqa: F401 -- must import before dispatch() calls below; see tools/__init__.py
from core.state import RetrievedChunk
from tools.registry import dispatch


def retrieve(
    query: str,
    tool_names: list[str] | None = None,
    max_results_per_tool: int = 5,
    debug_report: Callable[[str], None] | None = None,
) -> list[RetrievedChunk]:
    """Fan out `query` across the given tools (default: all registered
    web/news/arxiv/curated/github/reddit tools), then fuse + dedupe.

    tool_names defaults to a fixed list rather than tools.registry.list_tools()
    so a badly-behaved or slow tool added later doesn't silently get
    included in every retrieval call -- retrieval sources are opt-in.

    `debug_report`, if given, is called once per tool with a
    success/failure summary -- see decisions.md D-033. Without it, a
    failing tool (rate limit, malformed query, network error) was
    previously indistinguishable from "legitimately zero results,"
    since the bare except below intentionally doesn't fail the whole
    retrieval. That's still the right behavior for correctness; this
    just makes the silence optional rather than absolute.
    """
    if tool_names is None:
        # Per decisions.md D-034: reddit_search REMOVED from the
        # default set -- real-hardware testing showed it fails 100% of
        # the time (403 Blocked on every call, not intermittent), so
        # including it by default just spends a network round-trip on
        # a tool that structurally cannot succeed right now. The module
        # and its registration are left in place (opt-in via explicit
        # tool_names) in case Reddit's blocking behavior changes or an
        # OAuth-based approach gets built later -- see the module
        # docstring in tools/reddit_search.py for the caveat that was
        # already flagged (D-031) before this was confirmed.
        tool_names = [
            "web_search",
            "news_search",
            "arxiv_search",
            "curated_search",
            "github_search",
        ]

    all_chunks: list[RetrievedChunk] = []
    for name in tool_names:
        try:
            chunks = dispatch(name, query=query, max_results=max_results_per_tool)
            all_chunks.extend(chunks)
            if debug_report:
                debug_report(f"{name}: {len(chunks)} chunks")
        except Exception as exc:
            # A single tool failing (network error, parse error, etc.)
            # should not fail the whole retrieval -- other sources may
            # still have useful results. Sufficiency check (Phase 5)
            # handles the case where too many sources failed. The
            # exception itself is only surfaced via debug_report, never
            # raised or silently logged by default.
            if debug_report:
                debug_report(f"{name}: FAILED -- {type(exc).__name__}: {exc}")
            continue

    return dedupe(all_chunks)


def dedupe(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
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


def renumber_source_ids(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Reassigns every chunk's source_id to be globally unique across
    the whole list, preserving each chunk's original type prefix
    (news:, web:, arxiv:, etc.) for readability.

    Per decisions.md D-038: each individual tool call (tools/*.py)
    numbers its own results starting at 0 -- fine for a single retrieve()
    call, but the agentic path (rag/graph.py) accumulates results across
    multiple sub_queries AND multiple retry attempts, and dedupe() only
    checks (source, content) uniqueness, never source_id. Two genuinely
    different chunks from different retrieve() calls can end up sharing
    a literal source_id like "news:0" -- confusing to display, and a
    real correctness bug: citation_verifier.py and rag/synthesis.py both
    build source_id-keyed dicts/sets, which silently shadow one of the
    colliding chunks, risking a citation being checked against the
    WRONG source's text. Call this after dedupe() whenever chunks may
    have been accumulated across more than one retrieve() call -- not
    needed on the fast path, which only ever calls retrieve() once.
    """
    counters: dict[str, int] = {}
    renumbered: list[RetrievedChunk] = []
    for chunk in chunks:
        prefix = chunk["source_id"].split(":", 1)[0]
        idx = counters.get(prefix, 0)
        counters[prefix] = idx + 1
        renumbered.append({**chunk, "source_id": f"{prefix}:{idx}"})
    return renumbered
