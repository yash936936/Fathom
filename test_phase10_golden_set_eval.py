import sys
from unittest.mock import patch

sys.path.insert(0, "src")
sys.path.insert(0, "tests/eval")

from core.state import RetrievedChunk
from golden_set_eval import run_golden_set, format_report, GoldenSetReport, GoldenSetResult

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


# --- Test 1: off_domain query -> correctly classified as domain-refused ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    entries1 = [{"query": "Write a Python function to reverse a list.", "category": "off_domain"}]
    model1 = StubModel(['{"in_domain": false, "confidence": 0.95, "reason": "coding request"}'])
    report1 = run_golden_set(entries1, model1)
    check("off_domain query correctly classified as refused", report1.results[0].refused is True)
    check("off_domain refusal type is 'domain'", report1.results[0].refusal_type == "domain")
    check("off_domain_refusal_rate computed correctly (1/1 = 100%)", report1.off_domain_refusal_rate == 1.0)

# --- Test 2: answerable query -> full pipeline runs, not refused, has citations ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    entries2 = [{"query": "When was the transistor invented?", "category": "answerable"}]
    model2 = StubModel([
        '{"in_domain": true, "confidence": 0.95, "reason": ""}',  # domain_gate
        '{"answerable": true, "confidence": 0.9, "reason": ""}',  # fast-path answerability
        "Invented in 1947 [web:0].",  # synthesis
    ])
    report2 = run_golden_set(entries2, model2)
    check("answerable query correctly classified as NOT refused", report2.results[0].refused is False)
    check("answerable query answer has citations", report2.results[0].has_citations is True)
    check("answerable_false_positive_refusal_rate is 0% (correctly answered)", report2.answerable_false_positive_refusal_rate == 0.0)

# --- Test 3: false_premise query -> answerability refuses, distinct from domain refusal ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    entries3 = [{"query": "Why did the transistor get banned in 1960?", "category": "false_premise"}]
    model3 = StubModel([
        '{"in_domain": true, "confidence": 0.9, "reason": ""}',  # passes domain_gate
        '{"answerable": false, "confidence": 0.9, "reason": "no such ban occurred"}',  # answerability catches it
    ])
    report3 = run_golden_set(entries3, model3)
    check("false_premise query correctly classified as refused", report3.results[0].refused is True)
    check("false_premise refusal type is 'answerability', distinct from domain", report3.results[0].refusal_type == "answerability")
    check("false_premise_catch_rate computed correctly", report3.false_premise_catch_rate == 1.0)

# --- Test 4: low_evidence query with no citations, no caveat -> flagged as review candidate ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    entries4 = [{"query": "Some obscure unanswerable thing", "category": "low_evidence"}]
    model4 = StubModel([
        '{"in_domain": true, "confidence": 0.9, "reason": ""}',
        '{"answerable": true, "confidence": 0.9, "reason": ""}',
        "This is definitely true with total confidence, no sources needed.",  # no citations, no caveat -- the risky case
    ])
    report4 = run_golden_set(entries4, model4)
    candidates = report4.low_evidence_review_candidates
    check("uncited, uncaveated low_evidence answer flagged as review candidate", len(candidates) == 1)

# --- Test 4b: low_evidence query WITH a citation -> NOT flagged (has grounding) ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    entries4b = [{"query": "Some obscure thing with a source", "category": "low_evidence"}]
    model4b = StubModel([
        '{"in_domain": true, "confidence": 0.9, "reason": ""}',
        '{"answerable": true, "confidence": 0.9, "reason": ""}',
        "This is true [web:0].",
    ])
    report4b = run_golden_set(entries4b, model4b)
    check("cited low_evidence answer is NOT flagged as a review candidate", len(report4b.low_evidence_review_candidates) == 0)

# --- Test 5: a query that errors doesn't kill the whole run ---
class ExplodingModel:
    def chat(self, *a, **k):
        raise RuntimeError("simulated failure")

entries5 = [{"query": "will fail", "category": "answerable"}]
report5 = run_golden_set(entries5, ExplodingModel())
check("errored query recorded, not raised", len(report5.errors) == 1)
check("errored query excluded from answerable_false_positive_refusal_rate (no entries)", report5.answerable_false_positive_refusal_rate is None)

# --- Test 6: format_report doesn't crash on an empty report, includes the prd.md threshold ---
empty = GoldenSetReport()
formatted_empty = format_report(empty)
check("format_report handles an empty report without crashing", "N/A" in formatted_empty)

formatted1 = format_report(report1)
check("format_report cites the prd.md 95% threshold explicitly", "95%" in formatted1)
check("format_report shows PASS/FAIL against the threshold", "[PASS]" in formatted1 or "[FAIL]" in formatted1)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
