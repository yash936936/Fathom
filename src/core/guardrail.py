"""
core/guardrail.py — input and output rails.

Per docs/trd.md §5, the target framework is NeMo Guardrails. Phase 2 ships
a lightweight, dependency-free rail implementation instead -- see
docs/decisions.md D-013 for why, and for the explicit condition under
which this gets replaced/wrapped by NeMo Guardrails rather than extended
further by hand.

This module does NOT enforce domain scope -- that's core/domain_gate.py.
This module catches things domain_gate isn't designed to catch: prompt
injection patterns and obvious PII in the query (input rail), and
structural problems with the model's answer before it reaches the user
(output rail).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Heuristic patterns for common prompt-injection / jailbreak phrasing.
# Deliberately pattern-level, not an exhaustive list -- see the
# child-safety-style guidance in workflow.md about not over-fitting to
# specific phrasings. These are supplementary to domain_gate.py's
# classifier, not a replacement for it.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (?:(?:all|your|previous|prior)\s+)*instructions", re.I),
    re.compile(r"disregard (?:(?:all|your|previous|prior)\s+)*instructions", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"forget (everything|all|your instructions)", re.I),
    re.compile(r"reveal (your |the )?system prompt", re.I),
    re.compile(r"act as (if you (are|were)|an?)\s", re.I),
    re.compile(r"pretend (you are|to be)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"\bDAN\b"),  # common jailbreak persona shorthand
]

# Coarse PII patterns -- flag, don't attempt to be a full PII scanner.
# Purpose here is to avoid the query/answer round-tripping obvious
# sensitive data through logs/retrieval, not full compliance-grade
# redaction (that would be its own dedicated module if ever needed).
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


@dataclass
class RailResult:
    passed: bool
    flags: list[str] = field(default_factory=list)


def input_rail(query: str) -> RailResult:
    """Run before the domain gate consumes the query (or alongside it --
    order between input_rail and domain_gate doesn't matter, both are
    cheap and run before any retrieval/generation spend)."""
    flags: list[str] = []

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            flags.append(f"possible_injection:{pattern.pattern[:30]}")

    if _EMAIL_PATTERN.search(query):
        flags.append("pii_email_in_query")
    if _PHONE_PATTERN.search(query):
        flags.append("pii_phone_in_query")

    # Injection patterns are a hard fail -- an off-domain classifier
    # might still score a jailbreak attempt as "in domain" if it's
    # phrased as a research question wrapper. PII flags are advisory
    # only (don't refuse someone asking about their own email format
    # question) -- only the injection flags gate `passed`.
    passed = not any(f.startswith("possible_injection") for f in flags)
    return RailResult(passed=passed, flags=flags)


def output_rail(answer: str, require_citations: bool = True) -> RailResult:
    """Run on the model's answer before it's printed to the user. Phase 2
    scope: structural checks only (citation tags present, non-empty,
    not an obvious repeat of the injection patterns bouncing back). Full
    per-claim citation-entailment checking is verification/
    citation_verifier.py, Phase 6 -- not duplicated here.
    """
    flags: list[str] = []

    if not answer or not answer.strip():
        flags.append("empty_answer")

    if require_citations and "[" not in answer:
        # Cheap structural proxy for "does this look like it has
        # citation markers at all" -- real verification (does the
        # cited source actually support the claim) is Phase 6's job.
        flags.append("no_citation_markers")

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(answer):
            flags.append(f"injection_echo:{pattern.pattern[:30]}")

    passed = (
        "empty_answer" not in flags
        and "no_citation_markers" not in flags
        and not any(f.startswith("injection_echo") for f in flags)
    )
    return RailResult(passed=passed, flags=flags)
