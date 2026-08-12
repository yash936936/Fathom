"""
core/text_utils.py — small, dependency-free text helpers shared across
modules. Currently just keyword extraction, factored out of
rag/sufficiency.py's _fallback_query_from_gap (D-026) once a second
caller (tools/github_search.py, D-034) needed the same logic -- see
decisions.md D-034 for why this got consolidated now rather than left
duplicated.
"""

from __future__ import annotations

# Common filler/connective words to strip when reducing prose or a
# natural-language question down to a keyword-style search query.
# Deliberately a short, unglamorous list -- a bounded heuristic, not an
# NLP pipeline, and doesn't need to be exhaustive to be useful.
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "does", "do", "did",
    "not", "no", "none", "any", "of", "in", "on", "at", "to", "for",
    "and", "or", "but", "with", "about", "from", "by", "this", "that",
    "these", "those", "it", "its", "as", "be", "been", "being", "have",
    "has", "had", "provided", "evidence", "sources", "source", "given",
    "information", "covered", "cover", "discuss", "discussed", "topic",
    "content", "mentioned", "unrelated", "specific", "specifically",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "latest", "recent", "advances", "developments", "such", "like",
}


def simplify_to_keywords(text: str, max_words: int = 8) -> str:
    """Reduces `text` (prose, a gap explanation, a natural-language
    question) down to a bounded, keyword-style string suitable for a
    literal-match search engine (GitHub's repo search, or a re-query
    after a sufficiency check). Strips stopwords and very short tokens,
    caps the result length. This is intentionally crude -- see D-026's
    original note that a bounded heuristic here beats both (a) sending
    raw prose to a search API (B-006's mistake) and (b) giving up on
    refinement entirely when a model doesn't cooperate (B-007's gap).
    """
    words = [w.strip(".,!?;:\"'()") for w in text.lower().split()]
    keywords = [w for w in words if w and w not in STOPWORDS and len(w) > 2]
    return " ".join(keywords[:max_words])
