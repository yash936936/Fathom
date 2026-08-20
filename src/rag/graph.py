"""
rag/graph.py — the agentic path, wired with LangGraph.

Per docs/code_logic.md §4. Node order: PLANNER -> RETRIEVAL (fan-out) ->
RERANK_FILTER -> CURATOR -> SUFFICIENCY_CHECK -> (loop back to RETRIEVAL
if insufficient and under MAX_RETRIES, else) -> SYNTHESIS.

Per decisions.md D-045, Phase 6 is now fully wired: an ANSWERABILITY_PRE
node runs before PLANNER (cheap query-only false-premise check -- a hit
here skips planning/retrieval/synthesis entirely, since there's no point
spending any of that on a false-premise question). VERIFICATION (after
SYNTHESIS) re-checks answerability against what was actually retrieved,
runs citation_verifier, and runs self_consistency (agentic path only,
per D-006). core/guardrail.py's output_rail is still applied by the
caller, main.py, not inside the graph itself, so both paths share one
place that check runs.
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
from rag.retriever_hybrid import dedupe, renumber_source_ids, retrieve
from rag.sufficiency import should_retry, sufficiency_node
from rag.synthesis import generate
from verification import answerability, citation_verifier, self_consistency

_NOOP_REPORT: Callable[[str], None] = lambda _msg: None


def build_graph(
    model: FathomModel,
    top_k: int = 8,
    report: Callable[[str], None] | None = None,
    debug_report: Callable[[str], None] | None = None,
    conversation_context: str = "",
    enable_self_consistency: bool = False,
):
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

    def answerability_pre_node(state: ResearchState) -> ResearchState:
        # Cheap query-only check, per code_logic.md §6's "pre-retrieval"
        # half of the dual check. A hit here means skipping planner,
        # retrieval, curator, sufficiency, and synthesis entirely --
        # this is the one place in the agentic path where catching a
        # problem EARLY actually saves real cost, not just adds a
        # caveat after the fact (contrast with the post-retrieval
        # re-check below, in verification_node, which caveats rather
        # than discards an already-generated answer).
        report("Checking whether the question is answerable")
        verdict = answerability.check_answerability(state["original_query"], model)
        if verdict.ambiguous:
            state.setdefault("guardrail_flags", []).append("answerability_ambiguous_pre")
            state["answerable"] = True
        elif not verdict.answerable:
            state.setdefault("guardrail_flags", []).append(
                f"answerability_failed_pre:{verdict.reason}"
            )
            state["answerable"] = False
            state["answer"] = answerability.refusal_message(verdict.reason)
            state["citations"] = []
        else:
            state["answerable"] = True
        return state

    def planner_node(state: ResearchState) -> ResearchState:
        report("Planning sub-questions")
        return plan_node(state, model)

    def retrieval_node(state: ResearchState) -> ResearchState:
        sub_qs = state.get("sub_queries", [state["original_query"]])
        attempt = state.get("retry_count", 0) + 1
        report(f"Retrieving evidence (attempt {attempt})")
        if debug_report:
            debug_report(f"attempt {attempt} sub_queries: {sub_qs}")
        new_chunks = []
        for sub_query in sub_qs:
            new_chunks.extend(retrieve(sub_query, debug_report=debug_report))
        # Accumulate across retries rather than overwrite -- a retry that
        # discards prior evidence and starts from scratch wastes the
        # previous attempt's (expensive) retrieval entirely. dedupe()
        # collapses re-fetched duplicates from repeating the original
        # sub_queries. See decisions.md D-024 -- this was a real bug
        # found in the first live run, not a pre-planned design choice.
        combined = state.get("retrieved_chunks", []) + new_chunks
        # dedupe() then renumber_source_ids() -- see decisions.md D-038.
        # Order matters: dedupe first (drops true duplicates by content),
        # THEN renumber (guarantees the survivors have unique IDs, since
        # each individual retrieve() call numbers its own results from 0
        # and accumulation across attempts/sub_queries can otherwise
        # collide two different chunks onto the same "news:0"-style ID).
        state["retrieved_chunks"] = renumber_source_ids(dedupe(combined))
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
        result = sufficiency_node(state, model)
        if debug_report:
            debug_report(
                f"sufficient={result.get('sufficiency')} "
                f"gap={result.get('sufficiency_gap')!r} "
                f"refined_search_query={result.get('refined_search_query')!r}"
            )
        return result

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
        answer, citations = generate(
            state["original_query"], chunks, model, conversation_context=conversation_context
        )

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

    def verification_node(state: ResearchState) -> ResearchState:
        chunks = state.get("retrieved_chunks", [])

        # Post-retrieval answerability re-check, per code_logic.md §4/§6
        # -- "re-checked here for agentic multi-hop drift." Unlike the
        # pre-retrieval check, synthesis has already run at this point,
        # so a failure here CAVEATS the existing answer rather than
        # discarding the work already paid for.
        report("Re-checking answerability against retrieved evidence")
        a_verdict = answerability.check_answerability(state["original_query"], model, chunks=chunks)
        if debug_report:
            debug_report(
                f"answerability (post): answerable={a_verdict.answerable} "
                f"ambiguous={a_verdict.ambiguous} reason={a_verdict.reason!r}"
            )
        if a_verdict.ambiguous:
            state.setdefault("guardrail_flags", []).append("answerability_ambiguous_post")
        elif not a_verdict.answerable:
            state.setdefault("guardrail_flags", []).append(
                f"answerability_failed_post:{a_verdict.reason}"
            )
            state["answer"] += (
                f"\n\n[Note: on review, this question may rest on a "
                f"premise the retrieved evidence doesn't support -- "
                f"{a_verdict.reason}]"
            )

        # Per decisions.md D-006/D-032: heavy per-claim entailment check,
        # agentic path only, one batched call for the whole answer, not
        # per-claim. Phase 6.
        report("Verifying citations")
        citations = citation_verifier.verify_citations(state.get("citations", []), chunks, model)
        state["citations"] = citations

        _verified, unverified, unchecked = citation_verifier.summarize(citations)
        if debug_report:
            debug_report(f"citations: {_verified} verified, {unverified} unverified, {unchecked} unchecked")
        if unverified:
            state.setdefault("guardrail_flags", []).append(f"citations_unverified:{unverified}")
            state["answer"] += (
                f"\n\n[Note: {unverified} citation(s) in this answer could "
                f"not be confirmed against their source text on review -- "
                f"treat those specific claims with extra caution.]"
            )

        # Self-consistency: agentic path only, per D-006/D-032's same
        # cost-gating logic, and further gated by enable_self_consistency
        # since it's the single most expensive check in this node (a
        # full extra synthesis call) -- see verification/self_consistency.py
        # module docstring and D-045 for the real-hardware-latency caveat.
        if enable_self_consistency:
            report("Cross-checking answer consistency")
            consistency = self_consistency.sample_and_check(
                state["original_query"], chunks, state["answer"], model
            )
            if debug_report:
                debug_report(
                    f"self-consistency: checked={consistency.checked} "
                    f"flagged={sorted(consistency.flagged_facts)}"
                )
            if consistency.checked and consistency.flagged_facts:
                flagged_str = ", ".join(sorted(consistency.flagged_facts)[:5])
                state.setdefault("guardrail_flags", []).append(
                    f"self_consistency_flagged:{len(consistency.flagged_facts)}"
                )
                state["answer"] += (
                    f"\n\n[Note: on repeated generation, these specific "
                    f"details varied and may be less reliable than the "
                    f"rest of the answer: {flagged_str}.]"
                )

        return state

    def route_after_sufficiency(state: ResearchState) -> str:
        return "retry" if should_retry(state) else "synthesize"

    def route_after_answerability_pre(state: ResearchState) -> str:
        return "refused" if not state.get("answerable", True) else "continue"

    graph = StateGraph(ResearchState)
    graph.add_node("answerability_pre", answerability_pre_node)
    graph.add_node("planner", planner_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("rerank_filter", rerank_filter_node)
    graph.add_node("curator", curator_node)
    graph.add_node("sufficiency_check", sufficiency_check_node)
    graph.add_node("retry_increment", retry_increment_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("verification", verification_node)

    graph.set_entry_point("answerability_pre")
    graph.add_conditional_edges(
        "answerability_pre",
        route_after_answerability_pre,
        {"refused": END, "continue": "planner"},
    )
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
    graph.add_edge("synthesis", "verification")
    graph.add_edge("verification", END)

    return graph.compile()


def run_agentic(
    query: str,
    model: FathomModel,
    top_k: int = 8,
    report: Callable[[str], None] | None = None,
    debug_report: Callable[[str], None] | None = None,
    conversation_context: str = "",
    enable_self_consistency: bool = False,
) -> ResearchState:
    """Entry point for main.py -- builds and runs the graph for one
    query. Building the graph per-call (not cached) is cheap; it's
    control-flow wiring, not the expensive part (the LLM calls inside
    the nodes are).

    `enable_self_consistency`, default **False** as of D-045 §2 (changed
    from an initial default of True): code_logic.md §7 specs this
    feature, but each additional sample is a full extra synthesis call,
    and this project's own measured per-call latency (D-022/D-029:
    ~140-3277s, cause of variance still unresolved) makes shipping it
    on by default an unresolved cost decision, not a settled one. See
    verification/self_consistency.py's module docstring. Turn this on
    explicitly (per-call, or by flipping this default) once real-
    hardware timing data for this check specifically exists -- this is
    NOT the same open question as D-029's general latency variance;
    it's an additive cost on top of it that hasn't been measured at all
    yet.
    """
    from core.state import new_state

    compiled = build_graph(
        model,
        top_k=top_k,
        report=report,
        debug_report=debug_report,
        conversation_context=conversation_context,
        enable_self_consistency=enable_self_consistency,
    )
    initial_state = new_state(query)
    initial_state["path"] = "agentic"
    final_state = compiled.invoke(initial_state)
    return final_state
