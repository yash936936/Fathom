"""
core/router.py — adaptive complexity routing: fast path vs agentic path.

Per docs/code_logic.md §2: this is a heuristic classifier, NOT an LLM
call. Deliberate choice, not an oversight -- see docs/decisions.md D-020.
Given the latency situation (D-015/D-017/D-018), adding a third LLM call
per query (after domain_gate, before synthesis) just to decide routing
would make an already-slow pipeline worse for no accuracy benefit a
cheap heuristic can't already capture.
"""

from __future__ import annotations

import re

from core.state import ResearchState

# Heuristics, not ML -- see module docstring. Each is a cheap, explainable
# signal that a query needs multi-hop decomposition rather than a single
# retrieval pass.
_COMPARISON_WORDS = re.compile(r"\b(compare|versus|vs\.?|difference between)\b", re.I)
_MULTI_PART_WORDS = re.compile(r"\b(and also|as well as|in addition to)\b", re.I)
_RECENCY_WORDS = re.compile(r"\b(latest|recent|current|today|this week|this month|trend|trending)\b", re.I)

# A query with more than this many words is more likely to need
# decomposition -- long research questions tend to bundle several
# sub-questions even without explicit comparison language.
_LONG_QUERY_WORD_THRESHOLD = 25


def requires_recency(query: str) -> bool:
    """Separate from complexity -- a short query can still need
    recency-biased retrieval (rag/reranker.py's requires_recency param).
    """
    return bool(_RECENCY_WORDS.search(query))


def classify_complexity(query: str) -> str:
    """Returns "simple" or "complex". Simple queries go to the fast path
    (single retrieval pass); complex queries go to the agentic path
    (Phase 5 -- rag/graph.py, not yet built as of Phase 4).
    """
    word_count = len(query.split())

    if _COMPARISON_WORDS.search(query):
        return "complex"
    if _MULTI_PART_WORDS.search(query):
        return "complex"
    if word_count > _LONG_QUERY_WORD_THRESHOLD:
        return "complex"
    if query.count("?") > 1:
        return "complex"  # multiple explicit questions in one message

    return "simple"


def route(state: ResearchState) -> ResearchState:
    """Mutates and returns state with `path` and `requires_recency` set.
    Called after core/domain_gate.py confirms domain_ok=True -- routing
    an off-domain query is wasted work.
    """
    query = state["original_query"]
    state["path"] = classify_complexity(query)
    state["requires_recency"] = requires_recency(query)
    return state
