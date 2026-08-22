"""
tests/eval/citation_accuracy_eval.py — establishes and tracks the
"per-claim citation accuracy" metric named in trd.md §7 and required
by phases.md's Phase 6 exit criteria. See decisions.md D-048 and this
directory's README.md for scope (this is NOT Phase 10's full golden
set -- it exists to answer one specific question).

Metric definition (per D-048): of all citations the agentic path
actually produces across the query set, what fraction does
verification/citation_verifier.py's entailment check confirm as
genuinely supported by their cited source?

    accuracy = verified / (verified + unverified)

`unchecked` citations (verify_citations() never got a usable verdict --
parse failure, or a run that never reached verification) are tracked
separately and reported, but excluded from the accuracy ratio itself:
counting them as either correct or incorrect would misrepresent what
was actually confirmed one way or the other.

run_agentic() is called directly here, NOT run_query() / the router --
citation_verifier only runs on the agentic path (D-006/D-032), so this
harness forces that path for every query regardless of what the
router's complexity heuristic would have picked, since the whole point
is measuring that specific check.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rag.graph import run_agentic  # noqa: E402
from verification.citation_verifier import summarize  # noqa: E402

_QUERIES_PATH = Path(__file__).resolve().parent / "phase6_citation_queries.jsonl"
_LOG_PATH = Path(__file__).resolve().parents[2] / "docs" / "eval_log.md"


@dataclass
class QueryResult:
    query: str
    verified: int
    unverified: int
    unchecked: int
    error: str | None = None


@dataclass
class EvalReport:
    results: list[QueryResult] = field(default_factory=list)

    @property
    def total_verified(self) -> int:
        return sum(r.verified for r in self.results if r.error is None)

    @property
    def total_unverified(self) -> int:
        return sum(r.unverified for r in self.results if r.error is None)

    @property
    def total_unchecked(self) -> int:
        return sum(r.unchecked for r in self.results if r.error is None)

    @property
    def accuracy(self) -> float | None:
        denom = self.total_verified + self.total_unverified
        if denom == 0:
            return None
        return self.total_verified / denom

    @property
    def query_errors(self) -> list[QueryResult]:
        return [r for r in self.results if r.error is not None]


def load_queries(path: Path = _QUERIES_PATH) -> list[str]:
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            queries.append(json.loads(line)["query"])
    return queries


def run_eval(
    queries: list[str],
    model,
    top_k: int = 8,
    enable_self_consistency: bool = False,
    report=None,
) -> EvalReport:
    """Runs every query through the real agentic path (forced, per this
    module's docstring) and aggregates citation_verifier's verdicts.
    A per-query failure (e.g. a retrieval tool erroring out) is caught
    and recorded rather than aborting the whole run -- one bad query
    shouldn't discard every other query's real signal.
    """
    eval_report = EvalReport()
    for i, query in enumerate(queries, 1):
        if report:
            report(f"[{i}/{len(queries)}] {query}")
        try:
            final_state = run_agentic(
                query, model, top_k=top_k, enable_self_consistency=enable_self_consistency
            )
            citations = final_state.get("citations", [])
            verified, unverified, unchecked = summarize(citations)
            eval_report.results.append(
                QueryResult(query=query, verified=verified, unverified=unverified, unchecked=unchecked)
            )
        except Exception as exc:  # noqa: BLE001 -- a single query's failure
            # must not take down the whole eval run; every other query's
            # real signal is still worth keeping.
            eval_report.results.append(
                QueryResult(query=query, verified=0, unverified=0, unchecked=0, error=str(exc))
            )
    return eval_report


def format_report(eval_report: EvalReport) -> str:
    lines = ["Per-query results:"]
    for r in eval_report.results:
        if r.error is not None:
            lines.append(f"  ERROR  {r.query!r}: {r.error}")
        else:
            lines.append(
                f"  verified={r.verified} unverified={r.unverified} "
                f"unchecked={r.unchecked}  {r.query!r}"
            )
    lines.append("")
    lines.append(f"Total verified:   {eval_report.total_verified}")
    lines.append(f"Total unverified: {eval_report.total_unverified}")
    lines.append(f"Total unchecked:  {eval_report.total_unchecked}")
    acc = eval_report.accuracy
    lines.append(
        f"Per-claim citation accuracy: {acc:.1%}" if acc is not None
        else "Per-claim citation accuracy: N/A (no verified+unverified citations produced)"
    )
    if eval_report.query_errors:
        lines.append(f"Queries that errored: {len(eval_report.query_errors)}/{len(eval_report.results)}")
    return "\n".join(lines)


def append_to_log(eval_report: EvalReport, hardware_note: str = "(unspecified)") -> None:
    """Appends one dated entry to docs/eval_log.md -- this is what makes
    the metric "tracked" over time (per phases.md's Phase 6 exit
    criteria wording), not just computable once. Does not overwrite
    prior entries.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    acc = eval_report.accuracy
    acc_str = f"{acc:.1%}" if acc is not None else "N/A"
    entry = (
        f"\n### {timestamp}\n"
        f"**Hardware:** {hardware_note}\n"
        f"**Queries run:** {len(eval_report.results)} "
        f"({len(eval_report.query_errors)} errored)\n"
        f"**Per-claim citation accuracy:** {acc_str} "
        f"({eval_report.total_verified} verified / "
        f"{eval_report.total_unverified} unverified / "
        f"{eval_report.total_unchecked} unchecked)\n"
    )
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def main() -> int:
    from core.llm_backend import get_model, ModelNotFoundError

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"citation_accuracy_eval: {exc}", file=sys.stderr)
        return 2

    queries = load_queries()
    eval_report = run_eval(queries, model, report=lambda msg: print(msg, file=sys.stderr))
    print(format_report(eval_report))
    append_to_log(eval_report)
    print(f"\nLogged to {_LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
