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


def fake_retrieve(query, tool_names=None, max_results_per_tool=5):
    return [FAKE_CHUNK]


# --- Test 1: straight-through path, sufficient on first check, no retry ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic

    model = StubModel(
        [
            '{"sub_queries": ["fusion energy progress"], "requires_recency": true}',  # planner
            '{"sufficient": true, "gap": ""}',  # sufficiency check -- passes immediately
            "Fusion energy has progressed significantly [web:0].",  # synthesis
        ]
    )
    final_state = run_agentic("What's the latest fusion energy progress?", model)
    check("graph completes with sufficient=True on first pass", final_state.get("sufficiency") is True)
    check("graph completes with retry_count still 0", final_state.get("retry_count", 0) == 0)
    check("graph produces a non-empty answer", bool(final_state.get("answer")))
    check("all 3 scripted model calls were consumed (planner, sufficiency, synthesis)", len(model.call_log) == 3)

# --- Test 2: insufficient once, then sufficient -- retry loop actually cycles ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_2

    model2 = StubModel(
        [
            '{"sub_queries": ["fusion energy progress"], "requires_recency": true}',  # planner
            '{"sufficient": false, "gap": "need more specific recent data"}',  # 1st sufficiency check -- insufficient
            '{"sufficient": true, "gap": ""}',  # 2nd sufficiency check (after retry) -- sufficient
            "Fusion energy has progressed [web:0].",  # synthesis
        ]
    )
    final_state2 = run_agentic_2("What's the latest fusion energy progress?", model2)
    check("retry loop incremented retry_count exactly once", final_state2.get("retry_count") == 1)
    check("graph eventually reaches sufficient=True after retry", final_state2.get("sufficiency") is True)
    check("all 4 scripted model calls were consumed (retry loop actually ran)", len(model2.call_log) == 4)

# --- Test 3: always insufficient -- retry cap is respected, doesn't loop forever ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_3
    from rag.sufficiency import MAX_RETRIES

    always_insufficient = ['{"sufficient": false, "gap": "still missing data"}'] * (MAX_RETRIES + 1)
    model3 = StubModel(
        ['{"sub_queries": ["q"], "requires_recency": false}']
        + always_insufficient
        + ["Best-effort answer given incomplete evidence [web:0]."]
    )
    final_state3 = run_agentic_3("some query", model3)
    check(f"retry cap respected -- retry_count == MAX_RETRIES ({MAX_RETRIES})", final_state3.get("retry_count") == MAX_RETRIES)
    check("gap is surfaced in the final answer, not silently dropped", "missing data" in final_state3.get("answer", "") or "incomplete" in final_state3.get("answer", "").lower())

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
