"""
rag/synthesis.py — answer generation with forced per-claim citations.

Per docs/code_logic.md §3 (fast path) and §4 (agentic path, Phase 5).
This module implements the fast-path version now; the agentic path reuses
the same generate() function, so Phase 5 doesn't duplicate this logic --
it just calls generate() with a different (larger, curated) chunk set.

Citations are enforced by construction, not hoped for: the prompt
requires bracketed [source_id] tags, and every retrieved chunk's
source_id is listed explicitly so the model has a closed set of valid
IDs to cite rather than inventing its own. Full per-claim entailment
verification (does the cited source actually support the claim) is
Phase 6's job (verification/citation_verifier.py) -- this module only
guarantees citation tags are present and reference real source_ids, not
that the citations are accurate.
"""

from __future__ import annotations

import re

from core.llm_backend import FathomModel
from core.state import Citation, RetrievedChunk

_SYSTEM_PROMPT = """You are a research assistant. Answer the user's \
question using ONLY the provided sources below. Do not use any \
knowledge outside these sources.

Rules:
- Every factual claim MUST be followed by a citation tag like [source_id] \
referencing the exact source_id it came from.
- Only cite source_ids that are actually listed below -- never invent one.
- If the sources don't contain enough information to answer, say so \
explicitly rather than guessing.
- Be concise. Do not pad the answer with unnecessary caveats or repetition.
"""

_CITATION_TAG_PATTERN = re.compile(r"\[([a-zA-Z0-9_:.-]+)\]")

# Matches a sentence-ending punctuation mark followed by whitespace --
# used to find the last COMPLETE sentence boundary in a possibly-
# truncated answer. Deliberately simple (no abbreviation handling like
# "Dr." or "U.S." -- a real NLP sentence splitter is overkill here);
# worst case it trims one sentence more than strictly necessary, which
# is a much better failure mode than showing a dangling word fragment.
_SENTENCE_END_PATTERN = re.compile(r"[.!?]\s")


def _smooth_truncation(text: str) -> str:
    """If `text` ends mid-sentence (a hard max_tokens cap cut it off
    before a natural stopping point -- see decisions.md D-028, caught in
    real quick-mode output ending in "The U"), trim back to the last
    complete sentence instead of showing a dangling fragment. If there's
    no complete sentence to trim back to at all, mark the cutoff
    explicitly rather than silently presenting a fragment as complete.
    """
    stripped = text.rstrip()
    if not stripped:
        return stripped
    if stripped[-1] in ".!?":
        return stripped  # already ends cleanly, nothing to do

    matches = list(_SENTENCE_END_PATTERN.finditer(stripped))
    if matches:
        trimmed = stripped[: matches[-1].end()].rstrip()
        if trimmed:
            return trimmed

    # No complete sentence anywhere (e.g. max_tokens cut off during the
    # very first sentence) -- don't silently show a fragment as if it
    # were the whole answer.
    return stripped + " [response cut short]"


def _format_sources(chunks: list[RetrievedChunk]) -> str:
    lines = []
    for chunk in chunks:
        date_part = f" ({chunk['date']})" if chunk.get("date") else ""
        lines.append(f"[{chunk['source_id']}] {chunk['source']}{date_part}: {chunk['content']}")
    return "\n\n".join(lines)


def _extract_citations(answer: str, valid_source_ids: set[str]) -> list[Citation]:
    """Pulls every [source_id] tag out of the answer and pairs it with
    the sentence-ish chunk of text preceding it, so citation_verifier.py
    (Phase 6) has (claim, source_id) pairs to check rather than having
    to re-parse the raw answer itself.
    """
    citations: list[Citation] = []
    last_end = 0
    for match in _CITATION_TAG_PATTERN.finditer(answer):
        source_id = match.group(1)
        claim_text = answer[last_end:match.start()].strip()
        last_end = match.end()
        if not claim_text:
            continue
        citations.append(
            Citation(
                claim=claim_text,
                source_id=source_id,
                verified=None if source_id in valid_source_ids else False,
                # verified=False immediately (not just None) when the
                # model cited a source_id that isn't in the real set --
                # that's a structural failure Phase 6 doesn't need an
                # LLM call to catch, it's already known at parse time.
            )
        )
    return citations


def generate(
    query: str,
    chunks: list[RetrievedChunk],
    model: FathomModel,
    max_tokens: int = 512,
    on_token=None,
) -> tuple[str, list[Citation]]:
    """Core synthesis call, shared by the fast path (Phase 4) and the
    agentic path's SYNTHESIS node (Phase 5). Returns (answer_text,
    citations) rather than mutating ResearchState directly, so it stays
    testable/callable independent of the state-threading machinery.

    `on_token`, if given, is forwarded to FathomModel.chat() for live
    streaming output -- see decisions.md D-021. Citation extraction still
    runs on the complete answer after streaming finishes, since citation
    tags need to be matched against the full text, not token-by-token.
    """
    if not chunks:
        # No retrieved evidence at all -- do not let the model answer
        # from parametric memory dressed up as grounded. This is the
        # "explicit refusal, not silent fallback" principle from
        # code_logic.md §4's sufficiency-loop-exhaustion behavior,
        # applied here for the degenerate zero-evidence case too.
        return (
            "I wasn't able to find any sources for this question, so I "
            "can't give a grounded answer. Try rephrasing, or this may "
            "be too niche or recent for current sources.",
            [],
        )

    sources_block = _format_sources(chunks)
    user_prompt = (
        f"Sources:\n\n{sources_block}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the sources above, with [source_id] citations "
        "on every claim."
    )

    answer = model.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.3,
        on_token=on_token,
    )
    answer = _smooth_truncation(answer.strip())

    valid_ids = {c["source_id"] for c in chunks}
    citations = _extract_citations(answer, valid_ids)
    return answer, citations
