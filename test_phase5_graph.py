import sys
sys.path.insert(0, "src")

from unittest.mock import patch
from core.state import RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModel:
    def __init__(self, scripted_replies):
        self._queue = list(scripted_replies)
        self.call_log = []

    def chat(self, messages, max_tokens=200, temperature=0.0, stop=None, on_token=None):
        if not self._queue:
            raise AssertionError("StubModel ran out of scripted replies")
        reply = self._queue.pop(0)
        self.call_log.append(reply)
        return reply


FAKE_CHUNK = RetrievedChunk(
    source_id="web:0",
    content="Fusion energy research has made significant recent progress in plasma confinement technology",
    source="Test Source",
    url="http://example.com",
    date="2026-08-01",
    relevance_score=1.0,
)


def fake_retrieve(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    return [FAKE_CHUNK]


# --- Test 1: straight-through path, sufficient on first check, no retry ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic

    model = StubModel(
        [
            '{"sub_queries": ["fusion energy progress"], "requires_recency": true}',  # planner
            '{"sufficient": true, "gap": "", "search_query": ""}',  # sufficiency check -- passes immediately
            "Fusion energy has progressed significantly [web:0].",  # synthesis
            '[{"index": 0, "supported": true}]',  # verification
        ]
    )
    final_state = run_agentic("What's the latest fusion energy progress?", model)
    check("graph completes with sufficient=True on first pass", final_state.get("sufficiency") is True)
    check("graph completes with retry_count still 0", final_state.get("retry_count", 0) == 0)
    check("graph produces a non-empty answer", bool(final_state.get("answer")))
    check("all 4 scripted model calls were consumed (planner, sufficiency, synthesis, verification)", len(model.call_log) == 4)

# --- Test 2: insufficient once, then sufficient -- retry loop actually cycles ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_2

    model2 = StubModel(
        [
            '{"sub_queries": ["fusion energy progress"], "requires_recency": true}',  # planner
            '{"sufficient": false, "gap": "need more specific recent data", "search_query": "fusion energy 2026 progress"}',  # 1st sufficiency check -- insufficient
            '{"sufficient": true, "gap": "", "search_query": ""}',  # 2nd sufficiency check (after retry) -- sufficient
            "Fusion energy has progressed [web:0].",  # synthesis
            '[{"index": 0, "supported": true}]',  # verification
        ]
    )
    final_state2 = run_agentic_2("What's the latest fusion energy progress?", model2)
    check("retry loop incremented retry_count exactly once", final_state2.get("retry_count") == 1)
    check("graph eventually reaches sufficient=True after retry", final_state2.get("sufficiency") is True)
    check("all 5 scripted model calls were consumed (retry loop actually ran, plus verification)", len(model2.call_log) == 5)

# --- Test 3: always insufficient -- retry cap is respected, doesn't loop forever ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_3
    from rag.sufficiency import MAX_RETRIES

    always_insufficient = ['{"sufficient": false, "gap": "still missing data", "search_query": "query still missing"}'] * (MAX_RETRIES + 1)
    model3 = StubModel(
        ['{"sub_queries": ["q"], "requires_recency": false}']
        + always_insufficient
        + ["Best-effort answer given incomplete evidence [web:0]."]
        + ['[{"index": 0, "supported": true}]']  # verification
    )
    final_state3 = run_agentic_3("some query", model3)
    check(f"retry cap respected -- retry_count == MAX_RETRIES ({MAX_RETRIES})", final_state3.get("retry_count") == MAX_RETRIES)
    check("gap is surfaced in the final answer, not silently dropped", "missing data" in final_state3.get("answer", "") or "incomplete" in final_state3.get("answer", "").lower())

# --- Test 4: retry actually refines sub_queries with the gap, and evidence accumulates ---
# Regression test for the real bug found in the first live run (see
# decisions.md D-024): retries used to silently re-run identical
# sub_queries and discard prior evidence.
call_count = {"n": 0}


def incrementing_retrieve(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    call_count["n"] += 1
    return [
        RetrievedChunk(
            source_id=f"web:{call_count['n']}",
            content=f"Compare X and Y: distinct evidence chunk number {call_count['n']} relevant to {query}",
            source="s",
            url=None,
            date=None,
            relevance_score=1.0,
        )
    ]


with patch("rag.graph.retrieve", side_effect=incrementing_retrieve):
    from rag.graph import run_agentic as run_agentic_4

    model4 = StubModel(
        [
            '{"sub_queries": ["original query"], "requires_recency": false}',
            '{"sufficient": false, "gap": "missing fission reactor data", "search_query": "small modular reactor 2026"}',
            '{"sufficient": true, "gap": "", "search_query": ""}',
            "Final answer [web:1][web:2].",
            '[{"index": 0, "supported": true}, {"index": 1, "supported": true}]',  # verification
        ]
    )
    final_state4 = run_agentic_4("compare X and Y", model4)
    check(
        "retry appends the refined search_query (not the prose gap) as a new sub_query",
        "small modular reactor 2026" in final_state4.get("sub_queries", [])
        and "missing fission reactor data" not in final_state4.get("sub_queries", []),
    )
    check(
        "evidence accumulates across retries (3 chunks: 1 from attempt 1 + "
        "2 from attempt 2, which re-queries original AND the new "
        "search_query-based sub_query -- not overwritten down to 1)",
        len(final_state4.get("retrieved_chunks", [])) == 3,
    )

    # --- B-015 regression: source_id collisions must not survive
    # accumulation across retrieval attempts. Real bug caught on a live
    # run -- two genuinely different chunks ended up sharing the same
    # source_id (e.g. "news:0") since each individual tool call numbers
    # its own results starting at 0.
    final_ids = [c["source_id"] for c in final_state4.get("retrieved_chunks", [])]
    check(
        "B-015: no duplicate source_ids survive into the final accumulated chunk list",
        len(final_ids) == len(set(final_ids)),
    )

# --- Test 5: B-015, targeted -- a retrieve() stub that resets its
# source_id counter every call (mimicking real tools/*.py behavior,
# unlike incrementing_retrieve above which used a global counter and
# so never actually exercised the collision this bug produced) ---
def reset_per_call_retrieve(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    # Always returns "news:0" -- exactly like a real tool call would,
    # since each individual tools/*.py module numbers its own results
    # starting at 0 every time it's invoked.
    return [
        RetrievedChunk(
            source_id="news:0",
            content=f"distinct real content about {query}",
            source=f"Source for {query}",
            url=None,
            date=None,
            relevance_score=None,
        )
    ]


with patch("rag.graph.retrieve", side_effect=reset_per_call_retrieve):
    from rag.graph import run_agentic as run_agentic_5

    model5 = StubModel(
        [
            '{"sub_queries": ["query A"], "requires_recency": false}',
            '{"sufficient": false, "gap": "need more", "search_query": "query B"}',
            '{"sufficient": true, "gap": ""}',
            "Answer citing both [news:0][news:1].",
            '[{"index": 0, "supported": true}, {"index": 1, "supported": true}]',
        ]
    )
    final_state5 = run_agentic_5("original query", model5)
    ids5 = [c["source_id"] for c in final_state5.get("retrieved_chunks", [])]
    check(
        "B-015 (targeted): two chunks that would collide as 'news:0' both from "
        "real per-call-reset retrieve() calls end up with distinct source_ids",
        len(ids5) == 2 and len(set(ids5)) == 2,
    )
    contents5 = [c["content"] for c in final_state5.get("retrieved_chunks", [])]
    check(
        "B-015 (targeted): both distinct underlying chunks are preserved, not one shadowing the other",
        len(set(contents5)) == 2,
    )

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
