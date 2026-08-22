import sys
sys.path.insert(0, "src")

from verification.self_consistency import sample_and_check, _extract_facts, N_SAMPLES
from core.state import RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class ScriptedModel:
    """Returns each entry of `replies` in order, one per generate() call
    (each call to synthesis.generate() triggers exactly one chat() call
    since these chunks are non-empty)."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.call_count = 0

    def chat(self, messages, max_tokens=200, temperature=0.3, stop=None, on_token=None):
        reply = self.replies[self.call_count]
        self.call_count += 1
        return reply


CHUNKS = [
    RetrievedChunk(source_id="web:0", content="Founded in 1998 by Jane Smith in Austin.", source="s1", url=None, date=None, relevance_score=None),
]

# --- Test 1: fact extraction picks up numbers, years, entities ---
facts = _extract_facts("The company was founded in 1998 by Jane Smith, raising 50% more funding than expected.")
check("year extracted", "1998" in facts)
check("percentage/number extracted", "50%" in facts)
check("multi-word entity extracted", "Jane Smith" in facts)

# --- Test 2: consistent resample -> nothing flagged ---
model = ScriptedModel(["Founded in 1998 by Jane Smith [web:0]."])
result = sample_and_check(
    "When was it founded?", CHUNKS, "Founded in 1998 by Jane Smith [web:0].", model
)
check("checked ran (evidence + facts present)", result.checked is True)
check("consistent facts across samples -> nothing flagged", result.flagged_facts == set())
check("exactly N_SAMPLES - 1 extra generate() calls made", model.call_count == N_SAMPLES - 1)

# --- Test 3: divergent resample -> the differing fact is flagged ---
model2 = ScriptedModel(["Founded in 2001 by Jane Smith [web:0]."])
primary = "Founded in 1998 by Jane Smith [web:0]."
result2 = sample_and_check("When was it founded?", CHUNKS, primary, model2)
check("checked ran", result2.checked is True)
check("divergent year flagged", "1998" in result2.flagged_facts)
check("corroborated entity NOT flagged", "Jane Smith" not in result2.flagged_facts)

# --- Test 4: no chunks -> skipped entirely, no model calls ---
model3 = ScriptedModel(["should not be called"])
result3 = sample_and_check("q", [], "some answer with 1998", model3)
check("no chunks -> checked=False", result3.checked is False)
check("no chunks -> no model calls made", model3.call_count == 0)

# --- Test 5: primary answer has no extractable facts -> skipped, no model calls ---
model4 = ScriptedModel(["should not be called"])
result4 = sample_and_check("q", CHUNKS, "it's complicated and depends on context.", model4)
check("no facts in primary answer -> checked=False", result4.checked is False)
check("no facts -> no model calls made", model4.call_count == 0)

# --- Test 6: n_samples < 2 is a no-op ---
model5 = ScriptedModel(["should not be called"])
result5 = sample_and_check("q", CHUNKS, "Founded in 1998.", model5, n_samples=1)
check("n_samples < 2 -> checked=False", result5.checked is False)
check("n_samples < 2 -> no model calls made", model5.call_count == 0)

# --- B-020 (found on real hardware, D-050 follow-up): trailing
# sentence punctuation must NOT get folded into a number, and citation
# marker digits must NOT leak in as content facts ---
check("B-020: trailing comma stripped from a year ('2024,' -> '2024')", "2024" in _extract_facts("...in 2024, the...") and "2024," not in _extract_facts("...in 2024, the..."))
check("B-020: trailing period stripped from a number", "40" in _extract_facts("grew by 40. Next,") and "40." not in _extract_facts("grew by 40. Next,"))
check("B-020: thousands-separator number still matches in full", "1,200" in _extract_facts("raised $1,200 total"))
check("B-020: citation marker digit does not leak into facts", "5" not in _extract_facts("as shown [web:5]."))
check("B-020: multi-index citation marker digits do not leak into facts", "2" not in _extract_facts("per [news:2,4] reports.") and "4" not in _extract_facts("per [news:2,4] reports."))
check("B-020: genuine number right next to a citation tag still extracted", "2024" in _extract_facts("released in 2024 [web:0]."))

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
