"""
verification/citation_verifier.py — per-claim (claim, cited source)
entailment check: does the cited source actually support the claim, not
just "does a citation tag exist" (core/guardrail.py's output_rail
already does that cheaper structural check for every query).

Per decisions.md D-006: this is a HEAVY check (a real LLM call) and only
runs on the agentic path, never the fast path -- spend verification
budget where risk (multi-hop, higher-stakes queries) is highest, not
uniformly. Per D-032: batches ALL claims from one answer into a SINGLE
call rather than one call per claim -- at this project's measured
per-call cost (D-022/D-029), N separate entailment calls for N claims
would multiply an already-expensive synthesis call by N, which is a
materially different (much worse) cost profile than one extra call.
"""

from __future__ import annotations

import json

from core.llm_backend import FathomModel
from core.state import Citation, RetrievedChunk

_SYSTEM_PROMPT = """You verify whether cited sources actually support \
the claims made about them. For each numbered claim below, decide if \
the cited source text actually supports/entails that specific claim -- \
not just whether they're on the same general topic.

Respond with ONLY a JSON array, no other text, one object per claim in \
the same order given:
[{"index": 0, "supported": true or false}, ...]
"""


def _format_claims(citations: list[Citation], chunks_by_id: dict[str, RetrievedChunk]) -> str:
    lines = []
    for i, c in enumerate(citations):
        source = chunks_by_id.get(c["source_id"])
        source_text = source["content"][:300] if source else "(source not found)"
        lines.append(f"{i}. CLAIM: {c['claim']}\n   SOURCE [{c['source_id']}]: {source_text}")
    return "\n\n".join(lines)


def verify_citations(
    citations: list[Citation],
    chunks: list[RetrievedChunk],
    model: FathomModel,
) -> list[Citation]:
    """Returns a new citations list with `verified` resolved to True/
    False for every entry that was previously None (not yet checked).
    Entries already False (an unresolved source_id, set by
    rag/synthesis.py's _extract_citations at parse time) are left
    as-is -- no need to spend model budget re-confirming something
    already structurally known to be wrong.

    Fails open on parse failure: returns citations UNCHANGED (still
    None where unchecked) rather than guessing true or false -- a
    verification step that silently marks unchecked claims as "verified"
    on its own failure would be worse than not running at all.
    """
    to_check = [c for c in citations if c.get("verified") is None]
    if not to_check:
        return citations

    chunks_by_id = {c["source_id"]: c for c in chunks}
    prompt = _format_claims(to_check, chunks_by_id)

    raw = model.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max(80, 20 * len(to_check)),
        temperature=0.0,
    )

    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        parsed = json.loads(raw[start:end])
        verdicts = {int(item["index"]): bool(item["supported"]) for item in parsed}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return citations

    result: list[Citation] = []
    check_idx = 0
    for c in citations:
        if c.get("verified") is None:
            verdict = verdicts.get(check_idx)
            result.append({**c, "verified": verdict})
            check_idx += 1
        else:
            result.append(c)
    return result


def summarize(citations: list[Citation]) -> tuple[int, int, int]:
    """Returns (verified_count, unverified_count, unchecked_count).
    unverified = explicitly failed entailment or an unresolved
    source_id; unchecked = verify_citations() never got a usable
    verdict for it (parse failure, or not run at all)."""
    verified = sum(1 for c in citations if c.get("verified") is True)
    unverified = sum(1 for c in citations if c.get("verified") is False)
    unchecked = sum(1 for c in citations if c.get("verified") is None)
    return verified, unverified, unchecked
