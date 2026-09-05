"""
core/state.py — ResearchState: the typed object threaded through the
LangGraph agentic run (rag/graph.py) and reused by the fast path.

See docs/architecture.md §3 and docs/code_logic.md for the node-level
contract each field supports. Keep this in sync with code_logic.md — if a
field's meaning changes, log it in docs/decisions.md, not just here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class Citation(TypedDict):
    """One (claim -> source) mapping produced by synthesis, checked by
    verification/citation_verifier.py."""

    claim: str
    source_id: str
    verified: bool | None  # None = not yet checked


class RetrievedChunk(TypedDict):
    """A single piece of retrieved evidence, uniform across all tools
    (tools/web_search.py, tools/news_feed.py, tools/arxiv_feed.py,
    tools/vector_store.py)."""

    source_id: str
    content: str
    source: str  # human-readable origin, e.g. "arxiv:2501.01234" or URL
    url: str | None
    date: str | None  # ISO date if known; used for recency filtering
    relevance_score: float | None


class ResearchState(TypedDict, total=False):
    """Shared state threaded through a single query's processing, on both
    the fast path (single pass) and the agentic path (rag/graph.py).

    `total=False` because not every field is populated on every path —
    the fast path skips sub_queries/retry_count/tool_calls_made.
    """

    # -- input --
    original_query: str

    # -- domain gate / router (core/domain_gate.py, core/router.py) --
    domain_ok: bool
    domain_confidence: float
    domain_reason: str  # per decisions.md D-075 -- classify_domain()
    # always produces a reason string but check_domain() previously
    # discarded it, leaving no way to see WHY a query was refused
    # without guessing. Populated on every check_domain() call
    # (successful or ambiguous), empty string only on a parse failure.
    path: str  # "fast" | "agentic"

    # -- planning (rag/planner.py, agentic path only) --
    sub_queries: list[str]
    requires_recency: bool
    tools_needed: list[str]

    # -- retrieval (rag/retriever_hybrid.py, tools/*) --
    tool_calls_made: list[dict[str, Any]]
    retrieved_chunks: list[RetrievedChunk]

    # -- curation / sufficiency (rag/curator.py, rag/sufficiency.py) --
    sufficiency: bool
    sufficiency_gap: str | None  # human-readable explanation, for the
    # user-facing caveat -- NOT used as a search query (see B-006)
    refined_search_query: str | None  # short, query-shaped string for
    # re-retrieval on the next attempt, kept separate from
    # sufficiency_gap's prose so a retry never sends a full sentence to
    # a search API
    retry_count: int

    # -- synthesis (rag/synthesis.py) --
    answer: str
    citations: list[Citation]
    raw_synthesized_answer: str  # the UNMUTATED output of
    # rag.synthesis.generate(), before synthesis_node's own
    # sufficiency-gap note or any of verification_node's caveats are
    # appended to `answer`. Exists so
    # verification/self_consistency.py compares each resample against
    # what synthesis actually produced, not against `answer` after
    # Fathom's own injected notes have been glued onto it -- see B-020.

    # -- verification (verification/*) --
    answerable: bool
    guardrail_flags: list[str]


def new_state(original_query: str) -> ResearchState:
    """Construct a fresh ResearchState for one query. Prefer this over
    hand-building the dict so every session starts with consistent
    defaults (per workflow.md — don't let per-node code silently assume
    a key exists)."""

    return ResearchState(
        original_query=original_query,
        domain_ok=False,
        domain_confidence=0.0,
        domain_reason="",
        path="",
        sub_queries=[],
        requires_recency=False,
        tools_needed=[],
        tool_calls_made=[],
        retrieved_chunks=[],
        sufficiency=False,
        sufficiency_gap=None,
        refined_search_query=None,
        retry_count=0,
        answer="",
        citations=[],
        answerable=True,
        guardrail_flags=[],
    )


@dataclass
class ConversationTurn:
    """One turn in the short-term conversation buffer (memory/
    conversation_buffer.py, Phase 7). Defined here since it references
    ResearchState-shaped data; kept minimal until Phase 7 actually wires
    it up."""

    query: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
