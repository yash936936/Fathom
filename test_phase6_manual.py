import sys
sys.path.insert(0, "src")

from verification.citation_verifier import verify_citations, summarize
from core.state import Citation, RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModel:
    def __init__(self, scripted_reply):
        self.scripted_reply = scripted_reply
        self.call_count = 0

    def chat(self, messages, max_tokens=200, temperature=0.0, stop=None, on_token=None):
        self.call_count += 1
        return self.scripted_reply


CHUNKS = [
    RetrievedChunk(source_id="web:0", content="Fusion combines light nuclei to release energy.", source="s1", url=None, date=None, relevance_score=None),
    RetrievedChunk(source_id="web:1", content="The stock market rose 2% today.", source="s2", url=None, date=None, relevance_score=None),
]

# --- Test 1: batched verification, mixed verdicts ---
citations = [
    Citation(claim="Fusion releases energy from light nuclei", source_id="web:0", verified=None),
    Citation(claim="Fusion causes stock prices to rise", source_id="web:1", verified=None),
]
model = StubModel('[{"index": 0, "supported": true}, {"index": 1, "supported": false}]')
result = verify_citations(citations, CHUNKS, model)
check("first claim correctly verified true", result[0]["verified"] is True)
check("second claim correctly verified false (mismatched claim/source)", result[1]["verified"] is False)
check("exactly one batched LLM call for two claims, not two calls", model.call_count == 1)

# --- Test 2: citations already marked verified=False (unresolved source_id) are skipped, not re-checked ---
citations2 = [
    Citation(claim="Some claim", source_id="fake:99", verified=False),  # already known-bad, set by synthesis._extract_citations
]
model2 = StubModel("should not be called")
result2 = verify_citations(citations2, CHUNKS, model2)
check("already-False citation is left unchanged, not re-verified", result2[0]["verified"] is False)
check("model is never called when nothing needs checking", model2.call_count == 0)

# --- Test 3: fails open on unparseable verifier output ---
citations3 = [Citation(claim="Some claim", source_id="web:0", verified=None)]
model3 = StubModel("not valid json at all")
result3 = verify_citations(citations3, CHUNKS, model3)
check("unparseable verifier output leaves citations unchanged (still None, not guessed)", result3[0]["verified"] is None)

# --- Test 6 (found on real hardware, status.md Entry 034/035/038):
# debug_report must receive the RAW response on parse failure, so a
# truncated/malformed batch can actually be diagnosed instead of just
# silently failing open with no trace. ---
debug_messages = []
citations6 = [Citation(claim="Some claim", source_id="web:0", verified=None)]
model6 = StubModel("not valid json at all")
verify_citations(citations6, CHUNKS, model6, debug_report=lambda msg: debug_messages.append(msg))
check("debug_report is called on parse failure", len(debug_messages) == 1)
check("debug_report message includes the raw response text", "not valid json at all" in debug_messages[0])
check("debug_report message includes the batch size", "1 citations" in debug_messages[0])

# --- Test 7: no debug_report given -> no crash, same fail-open behavior as before ---
citations7 = [Citation(claim="Some claim", source_id="web:0", verified=None)]
model7 = StubModel("also not valid json")
result7 = verify_citations(citations7, CHUNKS, model7)  # debug_report omitted entirely
check("debug_report is optional -- omitting it doesn't break fail-open behavior", result7[0]["verified"] is None)

# --- Test 8: reproduces a real-hardware pattern -- a TRUNCATED multi-
# citation batch (valid JSON syntax cut off mid-array, exactly what a
# max_tokens overrun looks like) still fails open, and debug_report
# surfaces the truncated text so it's distinguishable from other kinds
# of malformed output on inspection. ---
debug_messages8 = []
citations8 = [
    Citation(claim="Claim A", source_id="web:0", verified=None),
    Citation(claim="Claim B", source_id="web:1", verified=None),
]
truncated = '[{"index": 0, "supported": true}, {"index": 1, "supp'  # cut off mid-token
model8 = StubModel(truncated)
result8 = verify_citations(citations8, CHUNKS, model8, debug_report=lambda msg: debug_messages8.append(msg))
check("truncated multi-citation batch still fails open (both stay None)", result8[0]["verified"] is None and result8[1]["verified"] is None)
check("debug_report captures the truncated raw text for real diagnosis", truncated in debug_messages8[0])

# --- Test 9 (B-021, found on real hardware, status.md Entry 046):
# model sometimes returns a flat [true, false, ...] array instead of
# the requested [{"index": N, "supported": bool}, ...] objects. This
# used to raise TypeError('bool' object is not subscriptable) inside
# the try block and fall through to fail-open, discarding verdicts the
# model actually gave. Now accepted and mapped positionally. ---
citations9 = [
    Citation(claim="Claim A", source_id="web:0", verified=None),
    Citation(claim="Claim B", source_id="web:1", verified=None),
]
model9 = StubModel("[false, true]")
result9 = verify_citations(citations9, CHUNKS, model9)
check("B-021: flat boolean array is accepted, not treated as a parse failure", result9[0]["verified"] is False and result9[1]["verified"] is True)
check("B-021: exactly one call made for the flat-array response", model9.call_count == 1)

# --- Test 10: flat boolean array with prose wrapped around it (the
# real observed raw response shape: "[\n  false,\n  false,\n  false,\n  true\n]") ---
citations10 = [
    Citation(claim="Claim A", source_id="web:0", verified=None),
    Citation(claim="Claim B", source_id="web:1", verified=None),
]
model10 = StubModel("[\n  false,\n  true\n]")
result10 = verify_citations(citations10, CHUNKS, model10)
check("B-021: whitespace-formatted flat boolean array parses correctly", result10[0]["verified"] is False and result10[1]["verified"] is True)

# --- Test 11: an EMPTY flat array still falls through cleanly (no
# crash from `all()` on an empty sequence vacuously being True) --
# falls to the object-shape branch, then fails open since there's
# nothing to map onto `to_check`. ---
citations11 = [Citation(claim="Claim A", source_id="web:0", verified=None)]
model11 = StubModel("[]")
result11 = verify_citations(citations11, CHUNKS, model11)
check("B-021: empty array does not crash, citation stays unchecked", result11[0]["verified"] is None)

# --- Test 12: the original object-shaped format still works exactly
# as before -- this fix must not regress the primary path. ---
citations12 = [Citation(claim="Claim A", source_id="web:0", verified=None)]
model12 = StubModel('[{"index": 0, "supported": true}]')
result12 = verify_citations(citations12, CHUNKS, model12)
check("B-021: original object-shaped verdicts still parse correctly (no regression)", result12[0]["verified"] is True)

# --- Test 4: summarize() counts correctly ---
mixed = [
    Citation(claim="a", source_id="web:0", verified=True),
    Citation(claim="b", source_id="web:0", verified=True),
    Citation(claim="c", source_id="web:1", verified=False),
    Citation(claim="d", source_id="web:1", verified=None),
]
verified, unverified, unchecked = summarize(mixed)
check("summarize counts verified/unverified/unchecked correctly", (verified, unverified, unchecked) == (2, 1, 1))

# --- Test 5: empty citations list is a no-op, no call made ---
model5 = StubModel("should not be called")
result5 = verify_citations([], CHUNKS, model5)
check("empty citations list makes no model call", model5.call_count == 0 and result5 == [])

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
