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
    content="Founded in 1998 by Jane Smith, the company reported 40% growth.",
    source="Test Source",
    url="http://example.com",
    date="2026-08-01",
    relevance_score=1.0,
)


def fake_retrieve(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    return [FAKE_CHUNK]


# --- Test 1: answerability_pre catches a false premise and short-circuits
# BEFORE planner/retrieval/synthesis run at all -- only one model call
# total should be made. ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve) as mock_retrieve:
    from rag.graph import run_agentic

    model = StubModel(
        ['{"answerable": false, "confidence": 0.95, "reason": "the event never happened"}'],
    )
    final_state = run_agentic("Why did XYZ Corp collapse in 2019?", model, enable_self_consistency=False)
    check("false-premise pre-check produces a refusal-style answer", "premise" in final_state.get("answer", "").lower())
    check("reason is surfaced in the answer", "event never happened" in final_state.get("answer", ""))
    check("only ONE model call made -- planner/retrieval/synthesis never ran", len(model.call_log) == 1)
    check("retrieve() was never called -- short-circuit happened before RETRIEVAL", mock_retrieve.call_count == 0)
    check("citations empty on the short-circuited refusal", final_state.get("citations") == [])
    check("guardrail_flags records why", any("answerability_failed_pre" in f for f in final_state.get("guardrail_flags", [])))

# --- Test 2: ambiguous (low-confidence) answerability_pre verdict passes
# through -- graph proceeds normally, just flagged. ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_2

    model2 = StubModel(
        [
            '{"answerable": false, "confidence": 0.2, "reason": "unclear"}',  # ambiguous -- low confidence
            '{"sub_queries": ["q"], "requires_recency": false}',
            '{"sufficient": true, "gap": "", "search_query": ""}',
            "Founded in 1998 [web:0].",
            '{"answerable": true, "confidence": 0.9, "reason": ""}',
            '[{"index": 0, "supported": true}]',
        ]
    )
    final_state2 = run_agentic_2("when was the company founded", model2, enable_self_consistency=False)
    check("ambiguous pre-check does NOT short-circuit", bool(final_state2.get("sufficiency")))
    check("ambiguous flag recorded", "answerability_ambiguous_pre" in final_state2.get("guardrail_flags", []))
    check("all 6 calls consumed -- full pipeline ran despite ambiguous pre-check", len(model2.call_log) == 6)

# --- Test 3: self-consistency wired into verification -- a divergent
# resample produces a caveat appended to the final answer, and consumes
# the expected extra model call. ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_3

    model3 = StubModel(
        [
            '{"answerable": true, "confidence": 0.9, "reason": ""}',  # answerability_pre
            '{"sub_queries": ["q"], "requires_recency": false}',  # planner
            '{"sufficient": true, "gap": "", "search_query": ""}',  # sufficiency
            "Founded in 1998 by Jane Smith [web:0].",  # synthesis (primary answer)
            '{"answerable": true, "confidence": 0.9, "reason": ""}',  # answerability post-check
            '[{"index": 0, "supported": true}]',  # citation verification
            "Founded in 2004 by Jane Smith [web:0].",  # self-consistency resample (divergent year)
        ]
    )
    final_state3 = run_agentic_3("when was it founded", model3, enable_self_consistency=True)
    check("self-consistency ran and consumed the extra resample call", len(model3.call_log) == 7)
    check("divergent fact flagged in the final answer", "1998" in final_state3.get("answer", "") and "reliable" in final_state3.get("answer", ""))
    check("guardrail_flags records the self-consistency flag", any("self_consistency_flagged" in f for f in final_state3.get("guardrail_flags", [])))

# --- Test 4: enable_self_consistency=False skips the resample call entirely ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic as run_agentic_4

    model4 = StubModel(
        [
            '{"answerable": true, "confidence": 0.9, "reason": ""}',
            '{"sub_queries": ["q"], "requires_recency": false}',
            '{"sufficient": true, "gap": "", "search_query": ""}',
            "Founded in 1998 by Jane Smith [web:0].",
            '{"answerable": true, "confidence": 0.9, "reason": ""}',
            '[{"index": 0, "supported": true}]',
        ]
    )
    final_state4 = run_agentic_4("when was it founded", model4, enable_self_consistency=False)
    check("enable_self_consistency=False -- no extra resample call, exactly 6 calls", len(model4.call_log) == 6)
    check("no self-consistency flag when disabled", not any("self_consistency_flagged" in f for f in final_state4.get("guardrail_flags", [])))

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
