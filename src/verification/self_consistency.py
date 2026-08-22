"""
verification/self_consistency.py — sample synthesis at a higher
temperature, compare key factual claims (numbers, dates, named
entities) across samples, and flag anything that doesn't reproduce
consistently as low-confidence rather than presenting it as certain.

Per docs/code_logic.md §7 and decisions.md D-006: AGENTIC PATH ONLY.
Each additional sample is a full extra rag/synthesis.py call -- at this
project's measured per-call cost (D-022: ~140-3277s observed, still an
open unresolved-cause variance per D-029), this is real latency added
to every agentic-path query, not a cheap check. N_SAMPLES is kept at
the minimum (2 total: the primary answer already produced by the
SYNTHESIS node, plus ONE additional resample) precisely because of
that cost -- see decisions.md D-045 for the explicit tradeoff writeup
and why this may be worth gating further once real-hardware timing
data exists for it specifically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.llm_backend import FathomModel
from core.state import RetrievedChunk
from rag.synthesis import generate

N_SAMPLES = 2  # total samples counting the primary answer -- i.e. this
# module generates N_SAMPLES - 1 ADDITIONAL calls. See module docstring
# on why this is kept at the observable minimum rather than the 2-3
# code_logic.md §7 suggests as a range.

SAMPLE_TEMPERATURE = 0.7  # higher than synthesis's default 0.3,
# deliberately: a genuinely uncertain claim needs room to actually vary
# across samples for this check to detect anything. Sampling at the
# default (low) temperature would make every resample nearly identical
# regardless of underlying uncertainty, defeating the point of this
# check entirely.

# Bounded, dependency-free "fact" extraction -- same "cheap heuristic
# beats an NLP dependency we can't afford" philosophy as
# core/text_utils.py (see trd.md §1's CPU/<6GB constraint). Not a
# semantic comparison: literal string sets, numbers/percentages, years,
# and capitalized multi-word entities.
# No trailing \b: \b only matches at a \w<->\W transition, and "%" is
# itself \W, so "50% " (digit -> % -> space) has no such transition
# after the %, meaning \b\d[\d,.]*%?\b would silently fail to match any
# number with a percent sign at all. The leading \b is safe (a digit is
# always \w, so it correctly anchors after whitespace/punctuation).
#
# The [\d,.]* run is wrapped as (?:[\d,.]*\d)? -- optional, but when
# present it must END in a digit. Without this, "in 2024, the..." would
# greedily consume the sentence-punctuation comma as part of the
# number, producing "2024," as a "fact" instead of "2024" -- see B-020.
# A genuine thousands-separator ("1,200") still matches in full, since
# the trailing digit requirement is satisfied by the final "0", not by
# excluding commas altogether.
_NUMBER_PATTERN = re.compile(r"\b\d(?:[\d,.]*\d)?%?")
_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
_ENTITY_PATTERN = re.compile(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3}\b")

# Citation tags like "[web:5]" or "[news:0,1]" must be stripped BEFORE
# fact extraction, not just left in -- otherwise _NUMBER_PATTERN's
# leading \b matches the digit right after the colon (":" is \W, the
# digit is \w, so there IS a boundary there), and citation INDEX
# numbers get treated as content facts. Two samples citing the same
# true claim from a different source, or in a different order, would
# then get flagged as "inconsistent" purely because of which source
# happened to end up as web:0 vs web:2 in that particular generation --
# noise entirely unrelated to whether the claim itself is reliable.
# Same pattern rag/synthesis.py's _CITATION_TAG_PATTERN uses, reused
# here for consistency rather than redefined slightly differently. See
# B-020.
_CITATION_TAG_PATTERN = re.compile(r"\[([a-zA-Z0-9_:.,\s-]+)\]")


def _extract_facts(text: str) -> set[str]:
    """Pulls a bounded, comparable set of "facts" out of one answer
    sample. Deliberately crude (literal strings, not normalized
    semantics) -- a fact that differs only in exact phrasing between
    samples (e.g. "the study" vs "this research") is NOT what this
    check is for; numbers, dates, and named entities are the concrete,
    checkable claims code_logic.md §7 calls out.

    Citation tags are stripped first -- see _CITATION_TAG_PATTERN's
    comment (B-020): a citation INDEX (which source got cited as
    web:0 vs web:2) is not a content fact, and including it produces
    noise unrelated to whether the underlying claim is reliable.
    """
    text = _CITATION_TAG_PATTERN.sub(" ", text)
    facts: set[str] = set()
    facts.update(_NUMBER_PATTERN.findall(text))
    facts.update(_YEAR_PATTERN.findall(text))
    facts.update(_ENTITY_PATTERN.findall(text))
    return facts


@dataclass
class ConsistencyResult:
    checked: bool  # False when the check didn't run at all (no evidence
    # to synthesize from, or nothing fact-like in the primary answer to
    # compare in the first place) -- distinct from checked=True with an
    # empty flagged_facts set, which means it ran and found no variance.
    flagged_facts: set[str] = field(default_factory=set)


def sample_and_check(
    query: str,
    chunks: list[RetrievedChunk],
    primary_answer: str,
    model: FathomModel,
    n_samples: int = N_SAMPLES,
) -> ConsistencyResult:
    """Generates n_samples - 1 ADDITIONAL synthesis samples at
    SAMPLE_TEMPERATURE (the primary answer, already produced by the
    SYNTHESIS node, counts as the first sample and is not regenerated),
    extracts comparable facts from each, and flags any fact present in
    the primary answer that isn't corroborated by every additional
    sample.

    Skips entirely (checked=False) when there's no evidence at all
    (rag/synthesis.generate's zero-chunk refusal is identical on every
    call -- resampling it would just confirm the same string N times
    for zero signal) or when the primary answer has no extractable
    facts to compare (a short qualitative answer -- not a failure of
    this check, just nothing for it to do).
    """
    if not chunks or n_samples < 2:
        return ConsistencyResult(checked=False)

    primary_facts = _extract_facts(primary_answer)
    if not primary_facts:
        return ConsistencyResult(checked=False)

    corroborated = set(primary_facts)
    for _ in range(n_samples - 1):
        sample_answer, _citations = generate(
            query, chunks, model, temperature=SAMPLE_TEMPERATURE
        )
        corroborated &= _extract_facts(sample_answer)

    flagged = primary_facts - corroborated
    return ConsistencyResult(checked=True, flagged_facts=flagged)
