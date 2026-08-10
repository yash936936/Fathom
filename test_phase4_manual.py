import sys
sys.path.insert(0, "src")

from core.router import classify_complexity, requires_recency, route
from core.state import new_state
from rag.synthesis import _extract_citations, generate
from core.state import RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


# --- router.classify_complexity ---
check("simple short query", classify_complexity("What is fusion energy?") == "simple")
check("comparison query is complex", classify_complexity("Compare fusion and fission energy") == "complex")
check("versus query is complex", classify_complexity("solar vs wind energy adoption trends") == "complex")
check("multi-part query is complex", classify_complexity("Tell me about AI safety and also about AI alignment research") == "complex")
check("double question mark is complex", classify_complexity("What is X? What is Y?") == "complex")
check(
    "very long query is complex",
    classify_complexity(" ".join(["word"] * 30)) == "complex",
)

# --- router.requires_recency ---
check("recency word detected", requires_recency("What are the latest trends in AI?") is True)
check("no recency word -> False", requires_recency("What is the capital of France?") is False)

# --- router.route mutates state correctly ---
state = new_state("What's the latest research on fusion?")
state = route(state)
check("route() sets path", state["path"] == "simple")
check("route() sets requires_recency", state["requires_recency"] is True)

# --- synthesis._extract_citations ---
chunks = [
    RetrievedChunk(source_id="web:0", content="c1", source="s1", url=None, date=None, relevance_score=None),
    RetrievedChunk(source_id="arxiv:1", content="c2", source="s2", url=None, date=None, relevance_score=None),
]
valid_ids = {c["source_id"] for c in chunks}

answer = "Fusion combines light nuclei [web:0]. Recent work shows progress [arxiv:1]."
citations = _extract_citations(answer, valid_ids)
check("extracts two citations", len(citations) == 2)
check("first citation maps to correct source_id", citations[0]["source_id"] == "web:0")
check("first citation verified is None (not yet checked, but valid id)", citations[0]["verified"] is None)

answer_bad = "Fusion is great [web:0]. Made up fact [fake:99]."
citations_bad = _extract_citations(answer_bad, valid_ids)
check(
    "citation to nonexistent source_id is immediately flagged verified=False",
    any(c["source_id"] == "fake:99" and c["verified"] is False for c in citations_bad),
)

answer_none = "This has no citations at all."
citations_none = _extract_citations(answer_none, valid_ids)
check("no citation tags -> empty citations list", citations_none == [])

# --- synthesis.generate with zero chunks -> explicit refusal, no model call ---
class _ShouldNotBeCalled:
    def chat(self, *a, **kw):
        raise AssertionError("model.chat() should not be called with zero chunks")

answer, citations = generate("some query", [], _ShouldNotBeCalled())
check("zero chunks -> explicit refusal without calling the model", "wasn't able to find any sources" in answer)
check("zero chunks -> empty citations", citations == [])

# --- D-028 regression: truncation smoothing against real observed output ---
from rag.synthesis import _smooth_truncation

real_truncated = (
    "Fusion energy is a potential method of electric power generation from heat "
    "released by nuclear fusion reactions [web:0]. Replicating this process on "
    "Earth could provide virtually limitless clean energy [web:2]. The U"
)
smoothed = _smooth_truncation(real_truncated)
check(
    "truncated mid-word fragment is dropped, not shown to the user",
    smoothed.endswith("[web:2].") and "The U" not in smoothed,
)

real_complete = "What we see as light is the result of a fusion reaction in the Sun [web:4]."
check(
    "already-complete answer passes through unchanged",
    _smooth_truncation(real_complete) == real_complete,
)

no_sentence_at_all = "Fusion energy is the proc"
check(
    "truncation with zero complete sentences is marked, not silently shown",
    "[response cut short]" in _smooth_truncation(no_sentence_at_all),
)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
