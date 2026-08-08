import sys
sys.path.insert(0, "src")

from rag.planner import plan, plan_node, PlanningError
from rag.curator import curate
from rag.sufficiency import check_sufficiency, should_retry, sufficiency_node, MAX_RETRIES
from core.state import new_state, RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModel:
    """Scriptable stub -- returns responses from a queue, one per call,
    so a test can simulate a multi-call sequence (e.g. insufficient,
    insufficient, then sufficient across a retry loop)."""

    def __init__(self, scripted_replies):
        self._queue = list(scripted_replies)

    def chat(self, messages, max_tokens=200, temperature=0.0, stop=None, on_token=None):
        if not self._queue:
            raise AssertionError("StubModel ran out of scripted replies")
        return self._queue.pop(0)


# --- planner.plan ---
model = StubModel(['{"sub_queries": ["q1", "q2"], "requires_recency": true}'])
sub_queries, requires_recency = plan("some complex question", model)
check("planner parses sub_queries and requires_recency", sub_queries == ["q1", "q2"] and requires_recency is True)

model = StubModel(["not valid json"])
try:
    plan("x", model)
    check("planner raises PlanningError on bad output", False)
except PlanningError:
    check("planner raises PlanningError on bad output", True)

model = StubModel(['{"sub_queries": ["only one"], "requires_recency": false}'])
state = new_state("test query")
state = plan_node(state, model)
check("plan_node sets state.sub_queries", state["sub_queries"] == ["only one"])

model = StubModel(["garbage output"])
state = new_state("test query")
state = plan_node(state, model)
check(
    "plan_node fails open to single-sub-query on parse failure",
    state["sub_queries"] == ["test query"] and "planner_parse_failure" in state["guardrail_flags"],
)

# --- curator.curate ---
chunks = [
    RetrievedChunk(source_id="a", content="Fusion energy research shows significant progress in plasma confinement", source="s", url=None, date=None, relevance_score=1.0),
    RetrievedChunk(source_id="b", content="x", source="s", url=None, date=None, relevance_score=1.0),  # too short
    RetrievedChunk(source_id="c", content="1234567890 !@#$%^&*() 1234567890 !@#$%^&*()", source="s", url=None, date=None, relevance_score=1.0),  # low alpha ratio
    RetrievedChunk(source_id="d", content="Completely unrelated content about cooking recipes and pasta dishes", source="s", url=None, date=None, relevance_score=1.0),
]
curated = curate(chunks, "fusion energy plasma research")
curated_ids = {c["source_id"] for c in curated}
check("curator keeps relevant, well-formed chunk", "a" in curated_ids)
check("curator drops too-short chunk", "b" not in curated_ids)
check("curator drops low-alpha-ratio chunk", "c" not in curated_ids)
check("curator drops zero-overlap chunk", "d" not in curated_ids)

# --- sufficiency.check_sufficiency + should_retry ---
model = StubModel(['{"sufficient": true, "gap": "", "search_query": ""}'])
sufficient, gap, search_query = check_sufficiency("q", [], model)
check("sufficiency parses sufficient=true", sufficient is True and gap == "" and search_query == "")

model = StubModel(['{"sufficient": false, "gap": "missing recent data", "search_query": "recent fusion energy news"}'])
state = new_state("q")
state["retry_count"] = 0
state = sufficiency_node(state, model)
check("sufficiency_node sets state fields", state["sufficiency"] is False and state["sufficiency_gap"] == "missing recent data")
check("sufficiency_node sets refined_search_query separately from gap", state["refined_search_query"] == "recent fusion energy news")

# --- B-006 regression: a prose "search_query" gets rejected, not used as-is ---
model = StubModel(['{"sufficient": false, "gap": "missing data", "search_query": "This is a full sentence explanation, not a real search query at all"}'])
state2 = new_state("q")
state2 = sufficiency_node(state2, model)
check(
    "prose-shaped search_query (>8 words) is rejected, not passed through",
    state2["refined_search_query"] is None and "sufficiency_search_query_rejected_not_query_shaped" in state2["guardrail_flags"],
)

# --- D-026 regression: real-hardware run showed the model sometimes
# returns an EMPTY search_query despite being told to always provide
# one -- confirm the LLM-free fallback kicks in using the real gap text
# observed in that run, rather than silently giving up on refinement. ---
real_world_gap = "Recent progress in fusion energy and specific advances in next-generation fission reactor designs are not covered in the provided evidence"
model3 = StubModel([f'{{"sufficient": false, "gap": "{real_world_gap}", "search_query": ""}}'])
state3 = new_state("q")
state3 = sufficiency_node(state3, model3)
check(
    "empty search_query falls back to a bounded, keyword-derived query from gap",
    state3["refined_search_query"] is not None
    and len(state3["refined_search_query"].split()) <= 8
    and "refined_search_query_derived_from_gap_fallback" in state3["guardrail_flags"],
)
check("should_retry True when insufficient and under cap", should_retry(state) is True)

state["retry_count"] = MAX_RETRIES
check("should_retry False once cap is hit, even if still insufficient", should_retry(state) is False)

state["sufficiency"] = True
state["retry_count"] = 0
check("should_retry False when sufficient regardless of retry_count", should_retry(state) is False)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
