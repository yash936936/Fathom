import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "tests/eval")

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
    source_id="web:0", content="The transistor was invented in 1947 by researchers at Bell Labs.",
    source="Test Source", url="http://example.com", date="2026-08-01", relevance_score=1.0,
)


def fake_retrieve(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    return [FAKE_CHUNK]


PIPELINE_REPLIES = [
    '{"answerable": true, "confidence": 0.9, "reason": ""}',  # answerability_pre
    '{"sub_queries": ["q"], "requires_recency": false}',       # planner
    '{"sufficient": true, "gap": "", "search_query": ""}',     # sufficiency
    "Invented in 1947 [web:0].",                                # synthesis
    '{"answerable": true, "confidence": 0.9, "reason": ""}',  # answerability post-check
]

with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from rag.graph import run_agentic
    from citation_accuracy_eval import (
        run_eval, format_report, append_to_log, EvalReport, QueryResult, load_queries, _QUERIES_PATH,
    )

    # --- Test 1: one query, citation verified -> accuracy 100% ---
    model1 = StubModel(PIPELINE_REPLIES + ['[{"index": 0, "supported": true}]'])
    report1 = run_eval(["When was the transistor invented?"], model1)
    check("one query produces one result", len(report1.results) == 1)
    check("verified count correct", report1.total_verified == 1)
    check("unverified count correct", report1.total_unverified == 0)
    check("accuracy computed as 100%", report1.accuracy == 1.0)
    check("no query errors", report1.query_errors == [])

    # --- Test 2: citation unverified -> accuracy reflects it ---
    model2 = StubModel(PIPELINE_REPLIES + ['[{"index": 0, "supported": false}]'])
    report2 = run_eval(["When was the transistor invented?"], model2)
    check("unverified citation counted", report2.total_unverified == 1)
    check("accuracy reflects the failure (0%)", report2.accuracy == 0.0)

    # --- Test 3: aggregation across multiple queries ---
    model3 = StubModel(
        PIPELINE_REPLIES + ['[{"index": 0, "supported": true}]']
        + PIPELINE_REPLIES + ['[{"index": 0, "supported": false}]']
    )
    report3 = run_eval(["transistor query A", "transistor query B"], model3)
    check("two queries aggregate to 1 verified + 1 unverified", report3.total_verified == 1 and report3.total_unverified == 1)
    check("aggregate accuracy is 50%", report3.accuracy == 0.5)

    # --- Test 4: a per-query exception is caught, not fatal to the run ---
    class ExplodingModel:
        def chat(self, *a, **k):
            raise RuntimeError("simulated tool failure")

    report4 = run_eval(["a query that will fail"], ExplodingModel())
    check("failing query recorded as an error, not raised", len(report4.query_errors) == 1)
    check("errored query excluded from accuracy denominator", report4.accuracy is None)

# --- Test 5: format_report doesn't crash on an empty report, and includes accuracy ---
empty_report = EvalReport()
formatted_empty = format_report(empty_report)
check("format_report handles zero results without crashing", "N/A" in formatted_empty)

formatted = format_report(report1)
check("format_report includes the accuracy percentage", "100.0%" in formatted)

# --- Test 6: append_to_log appends without overwriting, and reports correctly ---
with tempfile.TemporaryDirectory() as tmpdir:
    import citation_accuracy_eval as cae
    original_log_path = cae._LOG_PATH
    tmp_log = Path(tmpdir) / "eval_log.md"
    tmp_log.write_text("# existing content\n")
    cae._LOG_PATH = tmp_log
    try:
        append_to_log(report1, hardware_note="sandbox stub run")
        append_to_log(report3, hardware_note="sandbox stub run 2")
        final_content = tmp_log.read_text()
    finally:
        cae._LOG_PATH = original_log_path

check("append_to_log preserves prior content", "# existing content" in final_content)
check("append_to_log added both entries", final_content.count("Hardware:") == 2)
check("append_to_log records the accuracy figure", "100.0%" in final_content and "50.0%" in final_content)

# --- Test 7: load_queries reads the real fixture file correctly ---
real_queries = load_queries(_QUERIES_PATH)
check("real fixture file loads at least 10 queries", len(real_queries) >= 10)
check("loaded queries are non-empty strings", all(isinstance(q, str) and q for q in real_queries))

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
