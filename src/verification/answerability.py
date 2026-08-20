"""
verification/answerability.py — false-premise / unanswerable-framing
catch, per docs/code_logic.md §3 (fast path, post-retrieval) and
§4/§6 (agentic path, pre-retrieval AND post-retrieval).

Deliberately mirrors core/domain_gate.py's shape: a single cheap
classifier call (small max_tokens, temperature=0.0, same JSON-with-
confidence contract, same "fail open to ambiguous-and-flagged, never
silently refuse on a parse failure" rule). Unlike
verification/citation_verifier.py (a HEAVY per-claim entailment call,
agentic-path-only per decisions.md D-006/D-032), this check is cheap
enough to run on BOTH paths -- the whole point of code_logic.md §3's
placement (before synthesis) is to catch a false-premise question
*before* spending a synthesis call on it, on the fast path too, not
just the agentic one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.llm_backend import FathomModel
from core.state import RetrievedChunk

# Same threshold/semantics as domain_gate.py's CONFIDENCE_REFUSAL_THRESHOLD
# -- below this, treat the verdict as ambiguous rather than authoritative:
# pass through and flag, never silently refuse on a low-confidence call.
CONFIDENCE_THRESHOLD = 0.6

_SYSTEM_PROMPT_QUERY_ONLY = """You check whether a research question can \
be meaningfully answered, or whether it rests on a false premise -- it \
assumes something happened that didn't, asks about an event with no \
valid basis, contradicts a well-known timeline, or presupposes a fact \
that isn't true.

This is NOT about whether the answer is currently known or easy to \
find -- an obscure, niche, or forward-looking question is still \
answerable. Only flag questions whose premise itself is false.

Respond with ONLY a JSON object, no other text:
{"answerable": true or false, "confidence": a number from 0.0 to 1.0, \
"reason": "short phrase, empty string if answerable"}

Example of answerable=false: "Why did [some real organization] shut down \
in 2019?" when it never shut down. Example of answerable=true: "What are \
the latest developments in room-temperature superconductors?" (a hard, \
niche question -- but the premise itself is fine).
"""

_SYSTEM_PROMPT_WITH_EVIDENCE = """You check whether a research question \
rests on a false premise, using the retrieved evidence below as \
context. Flag it as unanswerable ONLY if the premise itself is false or \
contradicted by the evidence -- NOT merely because the evidence is thin \
or incomplete (that's a sufficiency/retrieval concern, not this check's \
job).

Respond with ONLY a JSON object, no other text:
{"answerable": true or false, "confidence": a number from 0.0 to 1.0, \
"reason": "short phrase, empty string if answerable"}
"""


@dataclass
class AnswerabilityVerdict:
    answerable: bool
    confidence: float
    reason: str
    ambiguous: bool  # True when confidence fell below CONFIDENCE_THRESHOLD


class AnswerabilityCheckError(RuntimeError):
    """Raised when the model's output can't be parsed as the expected
    JSON shape. Callers must treat this the same as an ambiguous
    verdict -- fail open to "pass through, flag", never fail open to a
    silent unflagged pass, and never fail closed to an unwarranted
    refusal on a parsing hiccup alone."""


def _format_evidence(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no evidence retrieved yet)"
    return "\n".join(f"- {c['source']}: {c['content'][:200]}" for c in chunks)


def classify_answerability(
    query: str,
    model: FathomModel,
    chunks: list[RetrievedChunk] | None = None,
) -> AnswerabilityVerdict:
    """Runs the classifier call. `chunks`, if given, switches to the
    evidence-aware prompt (post-retrieval re-check, per code_logic.md
    §4/§6's "re-checked against what was actually found" step) --
    otherwise this is the cheap pre-retrieval check on the query alone.
    """
    if chunks is None:
        system_prompt = _SYSTEM_PROMPT_QUERY_ONLY
        user_prompt = query
    else:
        system_prompt = _SYSTEM_PROMPT_WITH_EVIDENCE
        user_prompt = f"Question: {query}\n\nEvidence:\n{_format_evidence(chunks)}"

    raw = model.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=80,
        temperature=0.0,  # deterministic classification, same rationale
        # as domain_gate.classify_domain -- do not raise without logging
        # why in decisions.md.
    )

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
        answerable = bool(parsed["answerable"])
        confidence = float(parsed["confidence"])
        reason = str(parsed.get("reason", ""))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise AnswerabilityCheckError(
            f"Could not parse answerability output: {raw!r}"
        ) from exc

    confidence = max(0.0, min(1.0, confidence))
    ambiguous = confidence < CONFIDENCE_THRESHOLD
    return AnswerabilityVerdict(
        answerable=answerable, confidence=confidence, reason=reason, ambiguous=ambiguous
    )


def check_answerability(
    query: str,
    model: FathomModel,
    chunks: list[RetrievedChunk] | None = None,
) -> AnswerabilityVerdict:
    """Caller-facing entry point -- fails open on parse failure to
    "answerable, flagged" (mirrors domain_gate.check_domain's failure
    handling exactly): an unparseable verdict must never silently block
    a legitimate query, and must never silently pass through unflagged
    either.
    """
    try:
        return classify_answerability(query, model, chunks=chunks)
    except AnswerabilityCheckError:
        return AnswerabilityVerdict(
            answerable=True, confidence=0.0, reason="", ambiguous=True
        )


def refusal_message(reason: str) -> str:
    """User-facing message when a false premise is caught BEFORE any
    synthesis spend (pre-retrieval on the agentic path, or the fast
    path's single post-retrieval check when it fires with high
    confidence). Distinct in tone from a post-synthesis caveat (see
    rag/graph.py's verification_node, which appends a caveat rather
    than discarding an already-generated answer)."""
    detail = f" Specifically: {reason}." if reason else ""
    return (
        "This question appears to rest on a premise that isn't "
        f"supported.{detail} Consider rephrasing without that "
        "assumption, or ask a related question that doesn't depend on it."
    )
