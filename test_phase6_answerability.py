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

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
