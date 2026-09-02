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

# --- Test 4 (CORRECTED per a real discovery made while writing this
# test: output_rail actually runs UNCONDITIONALLY after BOTH the fast
# and agentic branches in main.run_query() -- not fast-path-only as
# D-060 first stated. This means an uncited answer with real chunks
# present is structurally UNREACHABLE through golden_set_eval.py's
# real pipeline (run_golden_set uses main.run_query()), not just
# unlikely. See decisions.md D-062 for the corrected finding. This
# test therefore exercises the property's LOGIC directly against a
# manually constructed result, the same pattern already used for the
# judge-assessment tests below -- there is no real pipeline path that
# reaches this scenario to integration-test against.) ---
manual_review_candidate = GoldenSetResult(
    query="Tell me about the transistor with total confidence",
    category="low_evidence", refused=False, refusal_type=None,
    has_citations=False, has_low_confidence_caveat=False, flags=[],
    answer="This is definitely true with total confidence, no sources needed.",
)
manual_report = GoldenSetReport(results=[manual_review_candidate])
check("uncited, uncaveated low_evidence answer flagged as review candidate (unit-level -- unreachable via the real pipeline, see D-062)", len(manual_report.low_evidence_review_candidates) == 1)

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

# --- Test 4c (D-062): the HONEST zero-evidence fallback must NOT be
# flagged as a hallucination-risk candidate -- it's the opposite of a
# risk, it's the most truthful possible response to missing evidence.
# Distinguishing this from output_rail's fallback is the whole point
# of the "zero_evidence" refusal_type. ---
def fake_retrieve_empty(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    return []

with patch("rag.graph.retrieve", side_effect=fake_retrieve_empty), patch("main.retrieve", side_effect=fake_retrieve_empty):
    entries4c = [{"query": "Some totally unfindable obscure thing", "category": "low_evidence"}]
    model4c = StubModel([
        '{"in_domain": true, "confidence": 0.9, "reason": ""}',  # domain_gate
        '{"answerable": true, "confidence": 0.9, "reason": ""}',  # answerability still runs with chunks=[] --
        # it's a meaningful input (checks the query alone), not a skip condition.
    ])  # generate() itself short-circuits on the empty chunks list before calling
    # model.chat() again -- that's the zero-evidence fallback under test.
    report4c = run_golden_set(entries4c, model4c)
    check("D-062: honest zero-evidence fallback is classified as refused", report4c.results[0].refused is True)
    check("D-062: refusal_type correctly identifies zero_evidence, distinct from output_rail", report4c.results[0].refusal_type == "zero_evidence")
    check("D-062: honest zero-evidence fallback is NOT flagged as a hallucination-risk candidate", len(report4c.low_evidence_review_candidates) == 0)

# --- Test 5: a query that errors doesn't kill the whole run ---
class ExplodingModel:
    def chat(self, *a, **k):
        raise RuntimeError("simulated failure")

entries5 = [{"query": "will fail", "category": "answerable"}]
report5 = run_golden_set(entries5, ExplodingModel())
check("errored query recorded, not raised", len(report5.errors) == 1)
check("errored query excluded from answerable_false_positive_refusal_rate (no entries)", report5.answerable_false_positive_refusal_rate is None)

# --- Test 6 (D-062, found on real hardware -- status.md Entry 044):
# a false_premise query whose answerability check is AMBIGUOUS (not a
# confident refusal) proceeds to synthesis per D-045's fail-open
# design; if synthesis then produces a no-citation answer,
# output_rail correctly intercepts it with the generic safety
# fallback. This IS a safe outcome and must be classified as refused
# -- missing this was the real root cause of golden_set_eval.py
# under-counting the false-premise catch rate on real data. ---
with patch("rag.graph.retrieve", side_effect=fake_retrieve), patch("main.retrieve", side_effect=fake_retrieve):
    entries6 = [{"query": "Why did the transistor get banned in 1960?", "category": "false_premise"}]
    model6 = StubModel([
        '{"in_domain": true, "confidence": 0.9, "reason": ""}',  # passes domain_gate
        '{"answerable": false, "confidence": 0.3, "reason": "no such ban occurred"}',  # AMBIGUOUS (low confidence) -- does NOT short-circuit
        "There was indeed such a ban, according to general knowledge.",  # synthesis produces a NO-CITATION answer
    ])
    report6 = run_golden_set(entries6, model6)
    check("D-062: ambiguous-answerability + no-citation answer IS correctly classified as refused (via output_rail)", report6.results[0].refused is True)
    check("D-062: refusal_type correctly identifies output_rail as the mechanism, distinct from domain/answerability", report6.results[0].refusal_type == "output_rail")
    check("D-062: false_premise_catch_rate now correctly counts this as caught", report6.false_premise_catch_rate == 1.0)

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

# --- Test 13 (D-068): subtype-aware false-premise catch rate. A
# blended catch rate hides that pre_check_reliable and needs_evidence
# are caught by two different mechanisms -- confirm the breakdown is
# computed correctly and independently of the blended number. ---
subtype_report = GoldenSetReport(results=[
    GoldenSetResult(query="q1", category="false_premise", refused=True, refusal_type="domain", has_citations=False, has_low_confidence_caveat=False, flags=[], subtype="pre_check_reliable"),
    GoldenSetResult(query="q2", category="false_premise", refused=True, refusal_type="domain", has_citations=False, has_low_confidence_caveat=False, flags=[], subtype="pre_check_reliable"),
    GoldenSetResult(query="q3", category="false_premise", refused=False, refusal_type=None, has_citations=True, has_low_confidence_caveat=False, flags=[], subtype="needs_evidence"),
    GoldenSetResult(query="q4", category="false_premise", refused=True, refusal_type="answerability", has_citations=False, has_low_confidence_caveat=False, flags=[], subtype="needs_evidence"),
])
check("D-068: pre_check_reliable subset rate computed correctly (2/2 = 100%)", subtype_report.false_premise_catch_rate_by_subtype("pre_check_reliable") == 1.0)
check("D-068: needs_evidence subset rate computed correctly (1/2 = 50%)", subtype_report.false_premise_catch_rate_by_subtype("needs_evidence") == 0.5)
check("D-068: blended rate is still the plain average, unaffected by subtype logic (3/4 = 75%)", subtype_report.false_premise_catch_rate == 0.75)
check("D-068: unknown subtype returns None, not a crash or a false zero", subtype_report.false_premise_catch_rate_by_subtype("nonexistent") is None)

# --- Test 14: untagged entries don't get silently miscounted into a
# subtype bucket they don't belong to, and still count toward the
# blended rate normally. ---
mixed_report = GoldenSetReport(results=[
    GoldenSetResult(query="q1", category="false_premise", refused=True, refusal_type="domain", has_citations=False, has_low_confidence_caveat=False, flags=[], subtype=None),
    GoldenSetResult(query="q2", category="false_premise", refused=True, refusal_type="domain", has_citations=False, has_low_confidence_caveat=False, flags=[], subtype="pre_check_reliable"),
])
check("D-068: untagged entries don't get counted into a subtype bucket", len(mixed_report.by_subtype("false_premise", "pre_check_reliable")) == 1)
check("D-068: untagged entries still count toward the blended rate", mixed_report.false_premise_catch_rate == 1.0)

# --- Test 15: format_report includes the subtype breakdown lines when
# subtypes are present, and omits them cleanly when they aren't
# (backward compatible with a golden set that has no subtype field). ---
formatted_with_subtypes = format_report(subtype_report)
check("D-068: format_report shows the pre-check-reliable subset line", "pre-check-reliable subset (n=2): 100.0%" in formatted_with_subtypes)
check("D-068: format_report shows the needs-evidence subset line", "needs-evidence subset (n=2): 50.0%" in formatted_with_subtypes)

no_subtype_report = GoldenSetReport(results=[
    GoldenSetResult(query="q1", category="false_premise", refused=True, refusal_type="domain", has_citations=False, has_low_confidence_caveat=False, flags=[]),
])
formatted_no_subtypes = format_report(no_subtype_report)
check("D-068: format_report omits subtype lines cleanly when nothing is tagged", "subset (n=" not in formatted_no_subtypes)

# --- Test 16 (D-069): named diagnostic candidates -- WHICH query
# failed, not just how many. Real-hardware runs showed the aggregate
# rate alone forced a separate --debug re-run just to find out which
# query was the problem; these list them directly in one run. ---
diag_report = GoldenSetReport(results=[
    GoldenSetResult(query="Answerable Q that got wrongly refused", category="answerable", refused=True, refusal_type="answerability", has_citations=False, has_low_confidence_caveat=False, flags=[]),
    GoldenSetResult(query="Answerable Q that worked fine", category="answerable", refused=False, refusal_type=None, has_citations=True, has_low_confidence_caveat=False, flags=[]),
    GoldenSetResult(query="False premise that slipped through", category="false_premise", refused=False, refusal_type=None, has_citations=True, has_low_confidence_caveat=False, flags=[], subtype="needs_evidence"),
    GoldenSetResult(query="False premise correctly caught", category="false_premise", refused=True, refusal_type="domain", has_citations=False, has_low_confidence_caveat=False, flags=[], subtype="pre_check_reliable"),
])
check("D-069: answerable_false_positive_candidates lists exactly the wrongly-refused one", [r.query for r in diag_report.answerable_false_positive_candidates] == ["Answerable Q that got wrongly refused"])
check("D-069: false_premise_missed_candidates lists exactly the one that slipped through", [r.query for r in diag_report.false_premise_missed_candidates] == ["False premise that slipped through"])

formatted_diag = format_report(diag_report)
check("D-069: format_report shows the WRONGLY REFUSED line with the actual query text", "WRONGLY REFUSED: 'Answerable Q that got wrongly refused'" in formatted_diag)
check("D-069: format_report shows the MISSED line with the actual query text and subtype", "MISSED: 'False premise that slipped through', subtype=needs_evidence" in formatted_diag)
check("D-069: format_report does NOT list queries that behaved correctly", "worked fine" not in formatted_diag and "correctly caught" not in formatted_diag)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
