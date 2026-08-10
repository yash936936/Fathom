"""
rag/graph.py — the agentic path, wired with LangGraph.

Per docs/code_logic.md §4. Node order: PLANNER -> RETRIEVAL (fan-out) ->
RERANK_FILTER -> CURATOR -> SUFFICIENCY_CHECK -> (loop back to RETRIEVAL
if insufficient and under MAX_RETRIES, else) -> SYNTHESIS.

Phase 6's VERIFICATION and OUTPUT_GUARDRAIL nodes (answerability,
citation_verifier, self_consistency) are NOT wired in yet -- this graph
ends at synthesis, same grounding guarantees as the fast path
(core/guardrail.py's output_rail is applied by the caller, main.py, not
inside the graph itself, so both paths share one place that check runs).
"""

from __future__ import annotations

from typing import Callable

import tools  # noqa: F401 -- registers built-in tools, see tools/__init__.py
from langgraph.graph import END, StateGraph

from core.llm_backend import FathomModel
from core.state import ResearchState
from rag.curator import curate
from rag.planner import plan_node
from rag.reranker import rerank
from rag.retriever_hybrid import dedupe, retrieve
from rag.sufficiency import should_retry, sufficiency_node
from rag.synthesis import generate

_NOOP_REPORT: Callable[[str], None] = lambda _msg: None


def build_graph(model: FathomModel, top_k: int = 8, report: Callable[[str], None] | None = None):
    """Returns a compiled LangGraph graph. `model` is closed over by the
    node functions below rather than threaded through ResearchState,
    since it's infrastructure (the loaded model), not query-specific
    data -- keeping it out of the TypedDict state matches how
    core/llm_backend.py's singleton is used everywhere else in the app.

    `report`, if given, is called with a short stage-description string
    at the start of each node -- main.py wires this to either verbose
    stage-by-stage logging or a single-line spinner update (see
    core/ui.py, decisions.md D-027). Defaults to a no-op so build_graph()
    stays callable without a reporter (e.g. from tests).
    """
    report = report or _NOOP_REPORT

    def planner_node(state: ResearchState) -> ResearchState:
        report("Planning sub-questions")
        return plan_node(state, model)

    def retrieval_node(state: ResearchState) -> ResearchState:
        sub_qs = state.get("sub_queries", [state["original_query"]])
        attempt = state.get("retry_count", 0) + 1
        report(f"Retrieving evidence (attempt {attempt})")
        new_chunks = []
        for sub_query in sub_qs:
            new_chunks.extend(retrieve(sub_query))
        # Accumulate across retries rather than overwrite -- a retry that
        # discards prior evidence and starts from scratch wastes the
        # previous attempt's (expensive) retrieval entirely. dedupe()
        # collapses re-fetched duplicates from repeating the original
        # sub_queries. See decisions.md D-024 -- this was a real bug
        # found in the first live run, not a pre-planned design choice.
        combined = state.get("retrieved_chunks", []) + new_chunks
        state["retrieved_chunks"] = dedupe(combined)
        return state

    def rerank_filter_node(state: ResearchState) -> ResearchState:
        state["retrieved_chunks"] = rerank(
            state.get("retrieved_chunks", []),
            top_k=top_k,
            requires_recency=state.get("requires_recency", False),
        )
        return state

    def curator_node(state: ResearchState) -> ResearchState:
        state["retrieved_chunks"] = curate(
            state.get("retrieved_chunks", []), state["original_query"]
        )
        return state

    def sufficiency_check_node(state: ResearchState) -> ResearchState:
        report("Checking whether evidence is sufficient")
        return sufficiency_node(state, model)

    def retry_increment_node(state: ResearchState) -> ResearchState:
        # Separate tiny node (rather than folding into sufficiency_check)
        # so the retry-count bump is visible as its own graph step --
        # easier to reason about / log than a side effect buried in the
        # sufficiency judgment node.
        state["retry_count"] = state.get("retry_count", 0) + 1

        # THE ACTUAL "refine sub_queries using gap" step from
        # code_logic.md §4 -- see decisions.md D-024/D-025/D-026. Uses
        # `refined_search_query` (short, query-shaped, validated/derived
        # in rag/sufficiency.py), NOT `sufficiency_gap` (human-readable
        # prose, meant for the user-facing caveat only). B-006: the first
        # version of this fix appended raw prose as a "query," which sent
        # full sentences to search APIs and made retrieval worse.
        refined_query = state.get("refined_search_query")
        if refined_query:
            existing = state.get("sub_queries", [])
            if refined_query not in existing:
                state["sub_queries"] = existing + [refined_query]
        return state

    def synthesis_node(state: ResearchState) -> ResearchState:
        report("Generating final answer")
        chunks = state.get("retrieved_chunks", [])
        answer, citations = generate(state["original_query"], chunks, model)

        gap = state.get("sufficiency_gap")
        if gap and not state.get("sufficiency", True):
            # Retry cap was exhausted with evidence still judged
            # insufficient -- surface that explicitly per D-010's
            # loop-engineering pattern, don't silently present a
            # best-effort answer as if it were complete.
            answer += (
                f"\n\n[Note: evidence on this topic was incomplete after "
                f"{state.get('retry_count', 0)} search attempts. "
                f"Specifically missing: {gap}]"
            )

        state["answer"] = answer
        state["citations"] = citations
        return state

    def route_after_sufficiency(state: ResearchState) -> str:
        return "retry" if should_retry(state) else "synthesize"

    graph = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("rerank_filter", rerank_filter_node)
    graph.add_node("curator", curator_node)
    graph.add_node("sufficiency_check", sufficiency_check_node)
    graph.add_node("retry_increment", retry_increment_node)
    graph.add_node("synthesis", synthesis_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "retrieval")
    graph.add_edge("retrieval", "rerank_filter")
    graph.add_edge("rerank_filter", "curator")
    graph.add_edge("curator", "sufficiency_check")
    graph.add_conditional_edges(
        "sufficiency_check",
        route_after_sufficiency,
        {"retry": "retry_increment", "synthesize": "synthesis"},
    )
    graph.add_edge("retry_increment", "retrieval")
    graph.add_edge("synthesis", END)

    return graph.compile()


def run_agentic(
    query: str,
    model: FathomModel,
    top_k: int = 8,
    report: Callable[[str], None] | None = None,
) -> ResearchState:
    """Entry point for main.py -- builds and runs the graph for one
    query. Building the graph per-call (not cached) is cheap; it's
    control-flow wiring, not the expensive part (the LLM calls inside
    the nodes are).
    """
    from core.state import new_state

    compiled = build_graph(model, top_k=top_k, report=report)
    initial_state = new_state(query)
    initial_state["path"] = "agentic"
    final_state = compiled.invoke(initial_state)
    return final_state
