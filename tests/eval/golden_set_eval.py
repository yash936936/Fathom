"""
tests/eval/golden_set_eval.py — Phase 10 (phases.md, prd.md §5).

Scoped deliberately narrow: `prd.md` §5 lists five success criteria.
Two are ALREADY covered by existing tooling and this script does NOT
duplicate them:
  - "per-claim citation accuracy tracked" -- tests/eval/
    citation_accuracy_eval.py (D-048) + docs/eval_log.md already do
    this, with real tracked history.
  - "<6GB RAM / CPU-only" -- an architectural constraint (no GPU code
    anywhere), not something this script measures; a real memory
    profile during a real run is a separate, manual check.

This script measures the two criteria NOTHING currently covers:
  - "Refusal rate on off-domain queries >= 95%"
  - "Zero silent hallucination... (flagged low-confidence answers
    don't count as failures if they're correctly flagged)"

It also tracks two related, useful signals not named verbatim in
prd.md §5 but clearly implied by "zero silent hallucination":
false-premise catch rate (a confidently-answered false premise IS a
hallucination) and the false-positive-refusal rate on genuinely
answerable queries (an over-eager domain_gate is its own failure mode,
just the opposite direction from criterion #3).

IMPORTANT HONESTY NOTE on the "silent hallucination" check: this
script CANNOT actually verify factual correctness -- no component in
this codebase can, including citation_verifier.py's own entailment
check, which verifies a claim against a CITED source, not against
ground truth. What this script CAN do is flag the proxy signal that
would make silent hallucination possible: a confident answer with
NEITHER a citation tag NOR a low-confidence caveat. That's a candidate
for human review, not a confirmed hallucination -- the aggregate
report says exactly that, not more.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from core.domain_gate import REFUSAL_MESSAGE  # noqa: E402
from core.state import new_state  # noqa: E402
from main import run_query  # noqa: E402
from verification.answerability import refusal_message as _answerability_refusal_prefix  # noqa: E402

_GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.jsonl"
_LOG_PATH = Path(__file__).resolve().parents[2] / "docs" / "eval_log.md"

# Detecting the false-premise refusal by its distinctive opening
# phrase rather than an exact match -- refusal_message() interpolates
# a query-specific reason, so no two false-premise refusals are
# byte-identical the way the domain refusal always is.
_ANSWERABILITY_REFUSAL_PREFIX = _answerability_refusal_prefix("")[:40]

_CITATION_TAG_PATTERN = re.compile(r"\[[a-zA-Z0-9_]+:\d+\]")
_LOW_CONFIDENCE_CAVEAT_PATTERN = re.compile(r"\[Note:", re.IGNORECASE)

VALID_CATEGORIES = {"answerable", "off_domain", "false_premise", "low_evidence"}
PRD_REFUSAL_RATE_THRESHOLD = 0.95  # prd.md §5, verbatim


@dataclass
class GoldenSetResult:
    query: str
    category: str
    refused: bool
    refusal_type: str | None  # "domain" | "answerability" | None
    has_citations: bool
    has_low_confidence_caveat: bool
    flags: list[str]
    error: str | None = None


@dataclass
class GoldenSetReport:
    results: list[GoldenSetResult] = field(default_factory=list)

    def by_category(self, category: str) -> list[GoldenSetResult]:
        return [r for r in self.results if r.category == category and r.error is None]

    @property
    def off_domain_refusal_rate(self) -> float | None:
        entries = self.by_category("off_domain")
        if not entries:
            return None
        return sum(1 for r in entries if r.refused) / len(entries)

    @property
    def false_premise_catch_rate(self) -> float | None:
        entries = self.by_category("false_premise")
        if not entries:
            return None
        return sum(1 for r in entries if r.refused) / len(entries)

    @property
    def answerable_false_positive_refusal_rate(self) -> float | None:
        """Fraction of genuinely answerable queries that got INCORRECTLY
        refused -- the opposite failure mode from criterion #3. Lower
        is better (0.0 is ideal), unlike the other rates above."""
        entries = self.by_category("answerable")
        if not entries:
            return None
        return sum(1 for r in entries if r.refused) / len(entries)

    @property
    def low_evidence_review_candidates(self) -> list[GoldenSetResult]:
        """low_evidence entries with NEITHER a citation NOR a
        low-confidence caveat -- see module docstring's honesty note.
        These are candidates for human review, not confirmed
        hallucinations."""
        return [
            r for r in self.by_category("low_evidence")
            if not r.refused and not r.has_citations and not r.has_low_confidence_caveat
        ]

    @property
    def errors(self) -> list[GoldenSetResult]:
        return [r for r in self.results if r.error is not None]


def load_golden_set(path: Path = _GOLDEN_SET_PATH) -> list[dict]:
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry["category"] not in VALID_CATEGORIES:
                raise ValueError(f"Unknown category {entry['category']!r} in {entry!r}")
            entries.append(entry)
    return entries


def _classify_result(answer: str, flags: list[str]) -> tuple[bool, str | None]:
    if answer == REFUSAL_MESSAGE:
        return True, "domain"
    if answer.startswith(_ANSWERABILITY_REFUSAL_PREFIX):
        return True, "answerability"
    return False, None


def run_golden_set(
    entries: list[dict],
    model,
    mode: str = "deep",
    top_k: int = 8,
    report=None,
) -> GoldenSetReport:
    """Runs every entry through the REAL front door (main.run_query --
    domain_gate -> router -> path), not a forced-agentic shortcut like
    citation_accuracy_eval.py uses. That distinction matters here
    specifically: off_domain and false_premise detection both depend on
    the gates a forced-agentic run would bypass.
    """
    golden_report = GoldenSetReport()
    for i, entry in enumerate(entries, 1):
        query, category = entry["query"], entry["category"]
        if report:
            report(f"[{i}/{len(entries)}] ({category}) {query}")
        try:
            answer, _sources, flags, _streamed = run_query(
                query, model, mode=mode, max_tokens=512, top_k=top_k,
                report=report or (lambda _msg: None), stream_tokens=False,
            )
            refused, refusal_type = _classify_result(answer, flags)
            golden_report.results.append(
                GoldenSetResult(
                    query=query, category=category, refused=refused, refusal_type=refusal_type,
                    has_citations=bool(_CITATION_TAG_PATTERN.search(answer)),
                    has_low_confidence_caveat=bool(_LOW_CONFIDENCE_CAVEAT_PATTERN.search(answer)),
                    flags=flags,
                )
            )
        except Exception as exc:  # noqa: BLE001 -- one bad query must not
            # discard every other query's real signal, same reasoning as
            # citation_accuracy_eval.py's run_eval().
            golden_report.results.append(
                GoldenSetResult(
                    query=query, category=category, refused=False, refusal_type=None,
                    has_citations=False, has_low_confidence_caveat=False, flags=[], error=str(exc),
                )
            )
    return golden_report


def format_report(golden_report: GoldenSetReport) -> str:
    lines = ["Golden set results by category:"]

    odr = golden_report.off_domain_refusal_rate
    odr_str = f"{odr:.1%}" if odr is not None else "N/A"
    odr_pass = "PASS" if (odr is not None and odr >= PRD_REFUSAL_RATE_THRESHOLD) else "FAIL"
    lines.append(
        f"  [{odr_pass}] off-domain refusal rate: {odr_str} "
        f"(prd.md §5 threshold: >={PRD_REFUSAL_RATE_THRESHOLD:.0%})"
    )

    fpr = golden_report.false_premise_catch_rate
    lines.append(f"  false-premise catch rate: {f'{fpr:.1%}' if fpr is not None else 'N/A'} (no formal prd.md threshold, tracked as a hallucination-adjacent signal)")

    afp = golden_report.answerable_false_positive_refusal_rate
    lines.append(f"  answerable false-positive refusal rate: {f'{afp:.1%}' if afp is not None else 'N/A'} (lower is better -- 0% is ideal)")

    candidates = golden_report.low_evidence_review_candidates
    lines.append(f"  low-evidence queries needing human review: {len(candidates)}/{len(golden_report.by_category('low_evidence'))}")
    for r in candidates:
        lines.append(f"    -- {r.query!r} (no citation, no caveat -- NOT a confirmed hallucination, needs manual check)")

    if golden_report.errors:
        lines.append(f"  Queries that errored: {len(golden_report.errors)}/{len(golden_report.results)}")
        for r in golden_report.errors:
            lines.append(f"    ERROR ({r.category}) {r.query!r}: {r.error}")

    return "\n".join(lines)


def append_to_log(golden_report: GoldenSetReport, hardware_note: str = "(unspecified)") -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    odr = golden_report.off_domain_refusal_rate
    fpr = golden_report.false_premise_catch_rate
    afp = golden_report.answerable_false_positive_refusal_rate
    candidates = golden_report.low_evidence_review_candidates
    entry = (
        f"\n### {timestamp} (Golden set eval, D-059, Phase 10)\n"
        f"**Hardware:** {hardware_note}\n"
        f"**Entries run:** {len(golden_report.results)} "
        f"({len(golden_report.errors)} errored)\n"
        f"**Off-domain refusal rate:** {f'{odr:.1%}' if odr is not None else 'N/A'} "
        f"(prd.md threshold: >={PRD_REFUSAL_RATE_THRESHOLD:.0%})\n"
        f"**False-premise catch rate:** {f'{fpr:.1%}' if fpr is not None else 'N/A'}\n"
        f"**Answerable false-positive refusal rate:** {f'{afp:.1%}' if afp is not None else 'N/A'}\n"
        f"**Low-evidence review candidates:** {len(candidates)}/"
        f"{len(golden_report.by_category('low_evidence'))} "
        f"(NOT confirmed hallucinations -- flagged for manual review)\n"
    )
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def main() -> int:
    from core.llm_backend import get_model, ModelNotFoundError

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"golden_set_eval: {exc}", file=sys.stderr)
        return 2

    entries = load_golden_set()
    golden_report = run_golden_set(entries, model, report=lambda msg: print(msg, file=sys.stderr))
    print(format_report(golden_report))
    append_to_log(golden_report)
    print(f"\nLogged to {_LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
