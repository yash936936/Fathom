"""
rag/planner.py — query decomposition for the agentic path.

Per docs/code_logic.md §4 PLANNER node. One LLM call per invocation --
this is real cost given decisions.md D-022's accepted latency reality,
so the prompt is kept tight (small max_tokens) rather than open-ended.
"""

from __future__ import annotations

import json

from core.llm_backend import FathomModel
from core.state import ResearchState

_SYSTEM_PROMPT = """You are a research query planner. Break the user's \
question into 1-3 focused sub-questions that together would let someone \
answer it thoroughly. If the question is already narrow and doesn't need \
decomposition, return it as a single sub-question unchanged.

Also decide if the question needs RECENT/current information (true) or \
is about stable, established facts (false).

Respond with ONLY a JSON object, no other text:
{"sub_queries": ["...", "..."], "requires_recency": true or false}

Keep sub-questions concise and each independently searchable.
"""


class PlanningError(RuntimeError):
    """Raised when the planner's output can't be parsed. Callers should
    fail open to treating the original query as a single sub-query --
    same fail-open philosophy as core/domain_gate.py's
    DomainClassificationError, not a hard stop."""


def plan(query: str, model: FathomModel) -> tuple[list[str], bool]:
    raw = model.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        max_tokens=200,
        temperature=0.2,
    )
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
        sub_queries = [str(q) for q in parsed["sub_queries"] if str(q).strip()]
        requires_recency = bool(parsed.get("requires_recency", False))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise PlanningError(f"Could not parse planner output: {raw!r}") from exc

    if not sub_queries:
        raise PlanningError("Planner returned an empty sub_queries list")

    return sub_queries[:3], requires_recency  # cap at 3, matches system prompt's own instruction


def plan_node(state: ResearchState, model: FathomModel) -> ResearchState:
    """Mutates and returns state, per code_logic.md §4's PLANNER node
    contract. Fails open to a single-sub-query plan (the original query
    itself) rather than blocking the whole agentic run on a parse
    failure -- consistent with domain_gate.py's fail-open pattern.
    """
    try:
        sub_queries, requires_recency = plan(state["original_query"], model)
    except PlanningError:
        sub_queries = [state["original_query"]]
        requires_recency = state.get("requires_recency", False)
        state.setdefault("guardrail_flags", []).append("planner_parse_failure")

    state["sub_queries"] = sub_queries
    state["requires_recency"] = requires_recency
    return state
