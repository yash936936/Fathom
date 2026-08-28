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

_CITATION_TAG_PATTERN = re.compile(r"\[([a-zA-Z0-9_:.,\s-]+)\]")

# Per-chunk character cap for _format_sources(), added per decisions.md
# D-062 after three independent real "Requested tokens exceed context
# window" crashes. Budget: DEFAULT_N_CTX=8192 - DEEP_MODE_MAX_TOKENS=512
# = ~7680 tokens available for the whole prompt; reserving room for the
# system prompt, query, and (in --chat mode) conversation_context,
# ~5500-6000 tokens realistically remain for the sources block. At the
# default top_k=8, that's ~700-750 tokens/chunk -- 2000 characters is a
# conservative cut of that (roughly 500 tokens at ~4 chars/token),
# leaving real margin for tokenizer-estimate imprecision and for
# --top-k being raised above the default. Not a guarantee against every
# possible configuration (a much higher --top-k could still overflow),
# but it directly closes the failure mode actually observed three times
# on real hardware at the default settings.
_MAX_CHUNK_CHARS = 2000

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
        # Truncated to _MAX_CHUNK_CHARS -- see status.md Entry 034/035/
        # 044 and decisions.md D-062: real chunk content is unbounded
        # (a full news article or web page excerpt can run several
        # thousand characters), and with no cap here, top_k=8 real
        # chunks could push the total prompt past DEFAULT_N_CTX=8192,
        # crashing generate() entirely rather than degrading gracefully.
        # Confirmed as the actual root cause of three independent real
        # "Requested tokens exceed context window" crashes, all on
        # queries with several long real chunks.
        content = chunk["content"]
        if len(content) > _MAX_CHUNK_CHARS:
            content = content[:_MAX_CHUNK_CHARS] + "... [truncated]"
        lines.append(f"[{chunk['source_id']}] {chunk['source']}{date_part}: {content}")
    return "\n\n".join(lines)


def _extract_citations(answer: str, valid_source_ids: set[str]) -> list[Citation]:
    """Pulls every [source_id] tag out of the answer and pairs it with
    the sentence-ish chunk of text preceding it, so citation_verifier.py
    (Phase 6) has (claim, source_id) pairs to check rather than having
    to re-parse the raw answer itself.

    Per decisions.md D-039/D-040: two related real-run failures fixed
    with the same underlying fix. B-016: the model citing multiple
    sources for one claim back-to-back, e.g. "...global trends in
    fusion [web:0][web:1][web:2], ...", left no text BETWEEN adjacent
    tags, so the old logic's `if not claim_text: continue` silently
    dropped every tag after the first in any such run. B-017: the model
    also sometimes puts multiple IDs in ONE bracket,
    e.g. "[web:0, web:1]" -- the old character class didn't allow comma/
    whitespace inside a bracket at all, so these were dropped entirely,
    not just undercounted. Both patterns are normal ways a model
    multi-cites one claim, not edge cases; adjacent tags now reuse the
    last non-empty claim text, and each bracket's contents are split on
    comma into one citation per ID.
    """
    citations: list[Citation] = []
    last_end = 0
    last_claim_text = ""
    for match in _CITATION_TAG_PATTERN.finditer(answer):
        raw_ids = match.group(1)
        source_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
        claim_text = answer[last_end:match.start()].strip()
        last_end = match.end()
        if claim_text:
            last_claim_text = claim_text
        elif not last_claim_text:
            # No claim text has ever appeared before this tag (e.g. the
            # answer opens with a citation before any prose) -- nothing
            # sensible to attribute it to, so skip only in this genuine
            # edge case, not the common back-to-back-citations case.
            continue
        for source_id in source_ids:
            citations.append(
                Citation(
                    claim=last_claim_text,
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
    conversation_context: str = "",
    temperature: float = 0.3,
) -> tuple[str, list[Citation]]:
    """Core synthesis call, shared by the fast path (Phase 4) and the
    agentic path's SYNTHESIS node (Phase 5). Returns (answer_text,
    citations) rather than mutating ResearchState directly, so it stays
    testable/callable independent of the state-threading machinery.

    `on_token`, if given, is forwarded to FathomModel.chat() for live
    streaming output -- see decisions.md D-021. Citation extraction still
    runs on the complete answer after streaming finishes, since citation
    tags need to be matched against the full text, not token-by-token.

    `conversation_context`, if given (Phase 7, D-041), is prior Q&A
    history formatted by memory/conversation_buffer.py -- used ONLY here,
    at synthesis, so the model can resolve references like "that" or
    "the second one." Deliberately NOT threaded into domain_gate,
    router, or retrieval -- see D-041 for why injecting it earlier would
    break the router's word-count heuristic and pollute retrieval
    keyword-matching with old-topic terms.

    `temperature`, default 0.3 (unchanged from the original hardcoded
    value -- every existing caller keeps identical behavior). Exposed
    per decisions.md D-045 so verification/self_consistency.py (Phase 6)
    can request higher-temperature resampling of the SAME query/chunks
    without duplicating this whole function.
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
    context_block = f"Conversation so far:\n{conversation_context}\n\n" if conversation_context else ""
    user_prompt = (
        f"{context_block}"
        f"Sources:\n\n{sources_block}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the sources above, with [source_id] citations "
        "on every claim. If the conversation history above is relevant "
        "to resolving what this question refers to, use it -- but "
        "ground the answer itself only in the sources, never in prior "
        "answers alone."
    )

    answer = model.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        on_token=on_token,
    )
    answer = _smooth_truncation(answer.strip())

    valid_ids = {c["source_id"] for c in chunks}
    citations = _extract_citations(answer, valid_ids)
    return answer, citations
