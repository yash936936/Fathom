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
with patch("rag.graph.retrieve", side_effect=fake_retrieve), patch("main.retrieve", side_effect=fake_retrieve):
    entries1 = [{"query": "Write a Python function to reverse a list.", "category": "off_domain"}]
    model1 = StubModel(['{"in_domain": false, "confidence": 0.95, "reason": "coding request"}'])
    report1 = run_golden_set(entries1, model1)
    check("off_domain query correctly classified as refused", report1.results[0].refused is True)
    check("off_domain refusal type is 'domain'", report1.results[0].refusal_type == "domain")
    check("off_domain_refusal_rate computed correctly (1/1 = 100%)", report1.off_domain_refusal_rate == 1.0)

# --- Test 2: answerable query -> full pipeline runs, not refused, has citations ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve), patch("main.retrieve", side_effect=fake_retrieve):
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
with patch("rag.graph.retrieve", side_effect=fake_retrieve), patch("main.retrieve", side_effect=fake_retrieve):
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
with patch("rag.graph.retrieve", side_effect=fake_retrieve), patch("main.retrieve", side_effect=fake_retrieve):
    entries4 = [{"query": "Tell me about the transistor with total confidence", "category": "low_evidence"}]
    model4 = StubModel([
        '{"in_domain": true, "confidence": 0.9, "reason": ""}',
        '{"answerable": true, "confidence": 0.9, "reason": ""}',
        "This is definitely true with total confidence, no sources needed.",  # no citations, no caveat -- the risky case
    ])
    report4 = run_golden_set(entries4, model4)
    candidates = report4.low_evidence_review_candidates
    check("uncited, uncaveated low_evidence answer flagged as review candidate", len(candidates) == 1)

# --- Test 4b: low_evidence query WITH a citation -> NOT flagged (has grounding) ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve), patch("main.retrieve", side_effect=fake_retrieve):
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

# --- Test 7 (D-060): judge_low_evidence_candidates asks the judge
# model to independently assess review candidates -- the answer field
# must actually be populated for the judge to have content to read.
#
# NOTE: constructing GoldenSetResult directly here rather than driving
# it through run_golden_set()'s full real pipeline -- discovered while
# writing this test that core/guardrail.py's output_rail already
# blocks a confident, zero-citation answer when real chunks exist
# (require_citations=True), replacing it with the generic safety
# fallback BEFORE it could ever reach this heuristic. That's correct,
# reassuring production behavior, not a bug -- it just means this
# exact scenario can't be reproduced by scripting a raw synthesis
# reply through the full pipeline; the judge-assessment logic itself
# is what these tests exist to check, so testing it directly against
# a controlled GoldenSetResult is the right level, not a workaround.
from golden_set_eval import judge_low_evidence_candidates, format_hallucination_verdicts, HallucinationRiskVerdict, GoldenSetResult

manual_candidate = GoldenSetResult(
    query="Tell me about the transistor with total confidence",
    category="low_evidence", refused=False, refusal_type=None,
    has_citations=False, has_low_confidence_caveat=False, flags=[],
    answer="This is definitely true with total confidence, no sources needed.",
)
check("GoldenSetResult.answer is populated with the real answer text", manual_candidate.answer == "This is definitely true with total confidence, no sources needed.")

class JudgeStubModel:
    def __init__(self, replies):
        self._queue = list(replies)
        self.calls = []

    def chat(self, messages, max_tokens=100, temperature=0.0):
        self.calls.append(messages)
        return self._queue.pop(0)

# --- Test 8: judge agrees the answer is overconfident ---
judge_model8 = JudgeStubModel(['{"overconfident": true, "reasoning": "makes a sweeping factual claim with no hedge or source"}'])
verdicts8 = judge_low_evidence_candidates([manual_candidate], judge_model8)
check("judge verdict correctly parsed as overconfident=True", verdicts8[0].overconfident is True)
check("judge reasoning captured", "sweeping" in verdicts8[0].reasoning)
check("judge was given the actual answer text, not a placeholder", "no sources needed" in judge_model8.calls[0][1]["content"])

# --- Test 9: judge disagrees with the heuristic flag (says NOT overconfident) ---
judge_model9 = JudgeStubModel(['{"overconfident": false, "reasoning": "the claim is mundane and unlikely to need sourcing"}'])
verdicts9 = judge_low_evidence_candidates([manual_candidate], judge_model9)
check("judge can disagree with the heuristic flag (overconfident=False)", verdicts9[0].overconfident is False)

# --- Test 10: judge parse failure on one candidate doesn't crash the batch ---
judge_model10 = JudgeStubModel(["not valid json"])
verdicts10 = judge_low_evidence_candidates([manual_candidate], judge_model10)
check("judge parse failure recorded as an error, not raised", verdicts10[0].error is not None)

# --- Test 11: format_hallucination_verdicts never claims a confirmed hallucination ---
formatted8 = format_hallucination_verdicts(verdicts8)
check("format_hallucination_verdicts explicitly states verdicts are NOT confirmed hallucinations", "not confirmed hallucinations" in formatted8.lower())
check("format_hallucination_verdicts shows the OVERCONFIDENT flag when the judge agrees", "OVERCONFIDENT" in formatted8)

formatted9 = format_hallucination_verdicts(verdicts9)
check("format_hallucination_verdicts shows disagreement distinctly from agreement", "judge disagrees" in formatted9)

# --- Test 12: empty candidate list doesn't crash ---
formatted_empty_verdicts = format_hallucination_verdicts([])
check("format_hallucination_verdicts handles zero candidates without crashing", "0/0" in formatted_empty_verdicts)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
