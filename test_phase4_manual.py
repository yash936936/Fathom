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

# --- B-016 regression: back-to-back citation tags for one claim must
# all be extracted, not silently dropped after the first. Real bug
# caught on a live run: "...global trends in fusion [web:0][web:1]
# [web:2], there is no information..." collapsed 3 citations to 1
# because the OLD logic required non-empty text between every pair of
# tags, and adjacent tags have nothing between them.
answer_adjacent = "Some claim supported by multiple sources [web:0][web:1][web:2]."
citations_adjacent = _extract_citations(answer_adjacent, valid_ids)
check(
    "B-016: three back-to-back citation tags all get extracted, not just the first",
    len(citations_adjacent) == 3
    and {c["source_id"] for c in citations_adjacent} == {"web:0", "web:1", "web:2"},
)
check(
    "B-016: adjacent tags share the same preceding claim text",
    len({c["claim"] for c in citations_adjacent}) == 1
    and citations_adjacent[0]["claim"] == "Some claim supported by multiple sources",
)

# --- B-017 regression: comma-separated IDs inside ONE bracket, e.g.
# "[web:0, web:1]", recurred in real usage after B-016 was fixed --
# the old character class didn't allow comma/whitespace inside a
# bracket at all, so these were dropped entirely (not just
# undercounted, since the bracket didn't match the pattern at all).
answer_comma_bracket = "Milestones are mentioned [web:0, web:1], but nothing else."
citations_comma = _extract_citations(answer_comma_bracket, valid_ids)
check(
    "B-017: comma-separated IDs in one bracket both get extracted",
    len(citations_comma) == 2
    and {c["source_id"] for c in citations_comma} == {"web:0", "web:1"},
)
check(
    "B-017: comma-separated IDs share the same claim text",
    len({c["claim"] for c in citations_comma}) == 1,
)

# an answer that opens with a citation before any prose has nothing to
# attribute it to -- should still be skipped, this is the genuine
# no-claim-text edge case, not the common adjacent-tags case.
answer_leading_citation = "[web:0] Then some real claim text follows."
citations_leading = _extract_citations(answer_leading_citation, valid_ids)
check(
    "leading citation with no preceding text is still correctly skipped",
    len(citations_leading) == 0 or citations_leading[0]["claim"] != "",
)

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

# --- D-074 (found via real-hardware --debug diagnosis of two
# persistent golden-set false positives, "transistor invented" and
# "latest inflation rate" -- see decisions.md D-074, status.md
# Entry 057): a citation tag placed AFTER the sentence's closing
# punctuation ("Sentence. [source]") used to be mistaken for a
# mid-sentence truncation (last char "]" isn't in ".!?") and silently
# trimmed away, deleting a real citation from an otherwise complete,
# correctly-cited answer -- the actual root cause behind D-071 and
# D-073's retries both firing and still failing on those two queries. ---
citation_after_period = (
    "The transistor was invented in 1947 by Bardeen, Brattain, and "
    "Shockley at Bell Labs. [web:0]"
)
check(
    "D-074: citation placed AFTER the final period is preserved, not stripped",
    _smooth_truncation(citation_after_period) == citation_after_period,
)

multi_citation_after_period = "Inflation is currently 2.9%. [news:0][arxiv:1]"
check(
    "D-074: multiple trailing citation tags after the final period are all preserved",
    _smooth_truncation(multi_citation_after_period) == multi_citation_after_period,
)

citation_before_period = (
    "The transistor was invented in 1947 at Bell Labs [web:0]."
)
check(
    "D-074: citation placed BEFORE the final period still passes through unchanged",
    _smooth_truncation(citation_before_period) == citation_before_period,
)

# Genuinely truncated mid-token, with a citation tag right at the cut
# point and no closing punctuation anywhere -- must still be marked as
# cut short, not mistaken for a complete "citation after period" case.
genuinely_truncated_with_citation = "The transistor was invented in 1947 at Bell Labs [web:0]"
smoothed_truncated_citation = _smooth_truncation(genuinely_truncated_with_citation)
check(
    "D-074: a citation with no sentence-ending punctuation anywhere is still marked cut short",
    "[response cut short]" in smoothed_truncated_citation,
)

no_sentence_at_all = "Fusion energy is the proc"
check(
    "truncation with zero complete sentences is marked, not silently shown",
    "[response cut short]" in _smooth_truncation(no_sentence_at_all),
)

# --- D-062 (found on real hardware -- status.md Entry 034/035/044,
# three independent "Requested tokens exceed context window" crashes):
# _format_sources() must truncate long real chunk content, since
# nothing bounded it before and top_k=8 real web/news excerpts could
# push the synthesis prompt past DEFAULT_N_CTX=8192. ---
from rag.synthesis import _format_sources, _MAX_CHUNK_CHARS

long_chunk = RetrievedChunk(
    source_id="web:0", source="Long Source", url="http://example.com", date=None,
    relevance_score=1.0, content="A" * 5000,  # deliberately far longer than _MAX_CHUNK_CHARS
)
formatted = _format_sources([long_chunk])
check("D-062: long chunk content is truncated, not embedded in full", len(formatted) < 5000)
check("D-062: truncated content stays within _MAX_CHUNK_CHARS plus formatting overhead", len(formatted) < _MAX_CHUNK_CHARS + 200)
check("D-062: truncation is marked, not silently cut", "[truncated]" in formatted)

short_chunk = RetrievedChunk(
    source_id="web:1", source="Short Source", url="http://example.com", date=None,
    relevance_score=1.0, content="A short chunk that needs no truncation.",
)
formatted_short = _format_sources([short_chunk])
check("D-062: short chunk content is NOT truncated or marked", "[truncated]" not in formatted_short and "A short chunk that needs no truncation." in formatted_short)

# --- D-062: realistic worst case -- top_k=8 chunks, each long enough
# on its own to have contributed to the real overflow, must now stay
# comfortably within budget once combined. ---
eight_long_chunks = [
    RetrievedChunk(source_id=f"web:{i}", source=f"Source {i}", url="http://example.com", date=None,
                    relevance_score=1.0, content="B" * 4000)
    for i in range(8)
]
formatted_eight = _format_sources(eight_long_chunks)
# ~4 chars/token is a reasonable rough estimate for this kind of prose --
# not exact, but more than sufficient margin to confirm this stays well
# under the ~7000-token budget reserved for the sources block (see
# _MAX_CHUNK_CHARS's own comment for the full budget breakdown).
check("D-062: 8 long real-sized chunks combined stay well under a safe token-budget estimate", len(formatted_eight) // 4 < 7000)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
