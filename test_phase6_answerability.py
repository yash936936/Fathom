import sys
sys.path.insert(0, "src")

from verification.answerability import (
    check_answerability,
    classify_answerability,
    refusal_message,
    AnswerabilityCheckError,
)
from core.state import RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModel:
    def __init__(self, scripted_reply):
        self.scripted_reply = scripted_reply
        self.call_count = 0
        self.last_messages = None

    def chat(self, messages, max_tokens=200, temperature=0.0, stop=None, on_token=None):
        self.call_count += 1
        self.last_messages = messages
        return self.scripted_reply


CHUNKS = [
    RetrievedChunk(source_id="web:0", content="The org is still operating as of 2026.", source="s1", url=None, date=None, relevance_score=None),
]

# --- Test 1: query-only (pre-retrieval) check, answerable ---
model = StubModel('{"answerable": true, "confidence": 0.95, "reason": ""}')
verdict = check_answerability("What are recent advances in battery chemistry?", model)
check("answerable=true parsed correctly", verdict.answerable is True)
check("not ambiguous at high confidence", verdict.ambiguous is False)
check("chunks=None uses query-only prompt (no 'Evidence:' in user message)", "Evidence:" not in model.last_messages[1]["content"])

# --- Test 2: query-only check, false premise detected ---
model2 = StubModel('{"answerable": false, "confidence": 0.9, "reason": "the org never shut down"}')
verdict2 = check_answerability("Why did XYZ Corp shut down in 2019?", model2)
check("false premise correctly flagged answerable=false", verdict2.answerable is False)
check("high confidence -> not ambiguous", verdict2.ambiguous is False)
check("reason carried through", verdict2.reason == "the org never shut down")

# --- Test 3: low confidence -> ambiguous, fails open (does not block) ---
model3 = StubModel('{"answerable": false, "confidence": 0.3, "reason": "unclear"}')
verdict3 = check_answerability("Some ambiguous question", model3)
check("low confidence marked ambiguous", verdict3.ambiguous is True)

# --- Test 4: post-retrieval check (chunks given) uses evidence-aware prompt ---
model4 = StubModel('{"answerable": true, "confidence": 0.8, "reason": ""}')
verdict4 = check_answerability("Is the org still active?", model4, chunks=CHUNKS)
check("chunks given -> evidence block present in prompt", "Evidence:" in model4.last_messages[1]["content"])
check("evidence content included", "still operating" in model4.last_messages[1]["content"])

# --- Test 5: unparseable output fails open to answerable+ambiguous, never raises to caller ---
model5 = StubModel("not json at all")
verdict5 = check_answerability("Any question", model5)
check("parse failure fails open: answerable=True", verdict5.answerable is True)
check("parse failure fails open: ambiguous=True (flagged)", verdict5.ambiguous is True)

# --- Test 6: classify_answerability (lower-level) raises on unparseable output ---
model6 = StubModel("garbage")
raised = False
try:
    classify_answerability("q", model6)
except AnswerabilityCheckError:
    raised = True
check("classify_answerability raises AnswerabilityCheckError on bad output", raised)

# --- Test 7: confidence clamped to [0, 1] ---
model7 = StubModel('{"answerable": true, "confidence": 1.7, "reason": ""}')
verdict7 = check_answerability("q", model7)
check("confidence clamped to 1.0", verdict7.confidence == 1.0)

# --- Test 8: refusal_message formatting ---
msg_with_reason = refusal_message("the event never happened")
msg_without_reason = refusal_message("")
check("refusal_message includes reason when given", "the event never happened" in msg_with_reason)
check("refusal_message is still a sensible sentence with empty reason", msg_without_reason.startswith("This question appears"))

# --- Test 9 (D-069): the evidence-based prompt now has TWO flagging
# criteria, not one -- confirm both are actually present, since real-
# hardware runs showed the original single-criterion version had a
# 0/5 real catch rate whenever a false premise reached this check.
# Import the module directly to inspect the actual prompt text sent to
# the model, not a paraphrase of it. ---
from verification import answerability as answerability_module  # noqa: E402

prompt_text = answerability_module._SYSTEM_PROMPT_WITH_EVIDENCE
check("D-069: criterion 1 (direct contradiction) still present", "contradicts the premise" in prompt_text)
check(
    "D-069: criterion 2 (substantial-but-silent evidence) is new and present",
    "never once corroborates the" in prompt_text,
)

# --- Test 10 (D-069): the ORIGINAL protection against flagging merely
# thin evidence must survive this change verbatim in spirit -- this is
# the exact regression risk flagged in decisions.md D-067/D-069. If a
# future edit accidentally drops this line while chasing a better
# catch rate, this test should fail. ---
check(
    "D-069: original thin-evidence protection is still present, not silently dropped",
    "sparse, incomplete, or barely" in prompt_text and "retrieval/sufficiency concern" in prompt_text,
)

# --- Test 11 (D-069): criterion 2 is explicitly scoped to SUBSTANTIAL
# evidence, not "any" evidence -- confirm the distinguishing word is
# actually in the prompt, since this exact distinction is what's
# supposed to prevent criterion 2 from degrading into "flag anything
# thin," which would reintroduce the D-066 answerable-false-positive
# problem this change is deliberately trying not to cause. ---
check(
    "D-069: criterion 2 explicitly requires SUBSTANTIAL evidence about the subject, not just any evidence",
    "substantial evidence" in prompt_text.lower(),
)

# --- Test 12: classify_answerability's actual call mechanics are
# unchanged by this prompt edit -- still parses the same JSON shape,
# still uses the evidence-aware prompt only when chunks are given. ---
chunk12: RetrievedChunk = {
    "source_id": "web:0", "source": "Test", "content": "Some real content.", "url": None,
}
model12 = StubModel('{"answerable": false, "confidence": 0.8, "reason": "no corroboration found"}')
verdict12 = check_answerability("Did X happen?", model12, chunks=[chunk12])
check("D-069: evidence-aware path still parses a false verdict correctly", verdict12.answerable is False)
check("D-069: evidence-aware path still carries the reason through", verdict12.reason == "no corroboration found")

# --- Test 13 (D-070): per-chunk evidence truncation raised 200 -> 500
# chars. Real-hardware runs showed D-069's criterion 2 never fired on
# its primary targets because the check literally couldn't see enough
# of each source to judge "substantial" coverage. Confirm the actual
# formatted evidence sent to the model reflects the new length, not
# the old one -- this is exactly the kind of thing a future "let's
# tidy this up" edit could silently revert without noticing why it
# mattered. ---
from verification.answerability import _format_evidence  # noqa: E402

long_content = "X" * 800  # longer than both the old (200) and new (500) limits
chunk13: RetrievedChunk = {
    "source_id": "web:0", "source": "Test Source", "content": long_content, "url": None,
}
formatted13 = _format_evidence([chunk13])
check("D-070: evidence formatting now includes MORE than the old 200-char limit", len(formatted13) > 200 + len("- Test Source: "))
check("D-070: evidence formatting is truncated at exactly 500 chars, not left unbounded", "X" * 500 in formatted13 and "X" * 501 not in formatted13)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
