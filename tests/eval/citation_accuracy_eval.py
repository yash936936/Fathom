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
    debug_report=None,
) -> EvalReport:
    """Runs every query through the real agentic path (forced, per this
    module's docstring) and aggregates citation_verifier's verdicts.
    A per-query failure (e.g. a retrieval tool erroring out) is caught
    and recorded rather than aborting the whole run -- one bad query
    shouldn't discard every other query's real signal.

    `debug_report`, if given, is threaded straight into run_agentic()'s
    own debug_report -- per-node progress (answerability verdicts,
    retrieval counts, sufficiency checks) becomes visible per query.
    Added after the first real-hardware run produced 5/12 queries with
    verified=unverified=unchecked=0 (a fully empty citations list) with
    no way to tell whether that came from answerability_pre correctly
    (or incorrectly) refusing, a genuine zero-evidence retrieval, or
    something else -- see status.md Entry 034. Without this, that
    question is structurally unanswerable from the eval output alone.
    """
    eval_report = EvalReport()
    for i, query in enumerate(queries, 1):
        if report:
            report(f"[{i}/{len(queries)}] {query}")
        try:
            final_state = run_agentic(
                query, model, top_k=top_k, enable_self_consistency=enable_self_consistency,
                report=report, debug_report=debug_report,
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


@dataclass
class JudgeComparisonResult:
    """One query's dual-judged outcome, per D-049's stated purpose:
    "explicitly treat any Qwen3-4B-vs-external-judge disagreement...
    as a signal worth logging." Qwen's verdicts are whatever
    citation_verifier.py already produced during the normal agentic
    run (D-006/D-032's runtime check); the judge's verdicts are a
    SEPARATE, independent re-check of the exact same (claim,
    source_id) pairs, computed after the fact by resetting `verified`
    to None and re-running verify_citations() with JudgeModel in place
    of FathomModel -- safe because verify_citations() only ever calls
    `model.chat(...)`, and JudgeModel implements that same interface
    (see judge_model.py's module docstring).
    """
    query: str
    qwen_verified: int
    qwen_unverified: int
    qwen_unchecked: int  # added after a real-hardware run (D-050
    # follow-up) where qwen(v=7,u=2) vs judge(v=5,u=5) looked like a
    # citation-count mismatch (9 vs 10) with no way to tell from the
    # printed output alone whether that was a bug or just an unchecked
    # citation on Qwen's side that the judge then resolved -- it was
    # the latter, but the report couldn't prove it. See status.md.
    judge_verified: int
    judge_unverified: int
    judge_unchecked: int
    agreements: int
    disagreements: int
    error: str | None = None


@dataclass
class JudgeComparisonReport:
    results: list[JudgeComparisonResult] = field(default_factory=list)

    @property
    def total_agreements(self) -> int:
        return sum(r.agreements for r in self.results if r.error is None)

    @property
    def total_disagreements(self) -> int:
        return sum(r.disagreements for r in self.results if r.error is None)

    @property
    def agreement_rate(self) -> float | None:
        denom = self.total_agreements + self.total_disagreements
        if denom == 0:
            return None
        return self.total_agreements / denom

    @property
    def qwen_accuracy(self) -> float | None:
        v = sum(r.qwen_verified for r in self.results if r.error is None)
        u = sum(r.qwen_unverified for r in self.results if r.error is None)
        return v / (v + u) if (v + u) else None

    @property
    def judge_accuracy(self) -> float | None:
        v = sum(r.judge_verified for r in self.results if r.error is None)
        u = sum(r.judge_unverified for r in self.results if r.error is None)
        return v / (v + u) if (v + u) else None

    @property
    def disagreeing_queries(self) -> list[JudgeComparisonResult]:
        """Queries with at least one disagreement, sorted by
        disagreement count descending. Added after the first real run
        (D-051 follow-up): the aggregate agreement rate (73.1% in that
        run) reads as evenly-distributed uncertainty, but the real
        per-query data showed ALL disagreements concentrated in just 2
        of 12 queries -- every other query with a real comparison
        agreed 100%. That distinction is the actionable part, and the
        aggregate number alone hides it completely.
        """
        return sorted(
            (r for r in self.results if r.error is None and r.disagreements > 0),
            key=lambda r: r.disagreements, reverse=True,
        )

    @property
    def qwen_only_zero_queries(self) -> list[JudgeComparisonResult]:
        """Queries where Qwen's own citation_verifier call produced
        zero checked citations (v=0, u=0) but left at least one
        unchecked (qwen_unchecked > 0) AND the judge found real
        verdicts on the same citations -- i.e. NOT a case of zero
        citations existing at all (that would show qwen_unchecked == 0
        too), specifically a Qwen-side parse failure the judge
        resolved. See D-051's finding about Qwen3-4B's structured-
        output reliability on this task.
        """
        return [
            r for r in self.results
            if r.error is None and r.qwen_verified == 0 and r.qwen_unverified == 0
            and r.qwen_unchecked > 0 and (r.judge_verified + r.judge_unverified) > 0
        ]

    @property
    def perfect_agreement_all_unsupported_queries(self) -> list[JudgeComparisonResult]:
        """Queries where both models agree, but agree everything is
        UNSUPPORTED (qwen_verified == judge_verified == 0 with real
        unverified counts on both sides). This is a RETRIEVAL/grounding
        quality signal, not a judge-reliability signal -- both models
        agreeing the sourcing is bad is a different finding than the
        two models disagreeing with each other."""
        return [
            r for r in self.results
            if r.error is None and r.qwen_verified == 0 and r.judge_verified == 0
            and r.qwen_unverified > 0 and r.judge_unverified > 0
        ]


def run_eval_with_judge(
    queries: list[str],
    model,
    judge_model,
    top_k: int = 8,
    report=None,
) -> JudgeComparisonReport:
    """Two-phase run, per D-049's sequential-loading constraint (never
    both models resident at once):

    Phase A: run every query through the real agentic path with `model`
    (Qwen3-4B) exactly as run_eval() does -- this is where
    citation_verifier.py's OWN verdicts get produced, same as any
    normal agentic run.

    Phase B: for the SAME (claim, source_id) pairs already collected in
    phase A, re-check with `judge_model` instead -- a fresh verdict,
    not a reuse of Qwen's. Compares the two per-citation and tallies
    agreement/disagreement.

    Caller is responsible for `model` already being loaded and for
    freeing it (del + gc.collect()) before constructing `judge_model`,
    per D-049 -- this function doesn't do that itself, since it doesn't
    own either model's lifecycle (see main_with_judge() below for the
    actual sequencing).
    """
    from verification.citation_verifier import verify_citations, summarize

    comparison = JudgeComparisonReport()
    for i, query in enumerate(queries, 1):
        if report:
            report(f"[{i}/{len(queries)}] {query}")
        try:
            final_state = run_agentic(query, model, top_k=top_k, enable_self_consistency=False)
            chunks = final_state.get("retrieved_chunks", [])
            qwen_citations = final_state.get("citations", [])
            qwen_verified, qwen_unverified, qwen_unchecked = summarize(qwen_citations)

            # Independent re-check: reset verified to None so
            # verify_citations() treats every citation as unchecked,
            # exactly as it would on a fresh run -- otherwise it would
            # skip everything, since Qwen already resolved them.
            judge_input = [{**c, "verified": None} for c in qwen_citations]
            judge_citations = verify_citations(judge_input, chunks, judge_model, debug_report=report)
            judge_verified, judge_unverified, judge_unchecked = summarize(judge_citations)

            agreements = 0
            disagreements = 0
            for qc, jc in zip(qwen_citations, judge_citations):
                qv, jv = qc.get("verified"), jc.get("verified")
                if qv is None or jv is None:
                    continue  # an unchecked verdict on either side isn't
                    # a comparable agreement/disagreement -- same
                    # exclusion reasoning as EvalReport.accuracy's
                    # handling of unchecked citations.
                if qv == jv:
                    agreements += 1
                else:
                    disagreements += 1

            comparison.results.append(
                JudgeComparisonResult(
                    query=query, qwen_verified=qwen_verified, qwen_unverified=qwen_unverified,
                    qwen_unchecked=qwen_unchecked, judge_verified=judge_verified,
                    judge_unverified=judge_unverified, judge_unchecked=judge_unchecked,
                    agreements=agreements, disagreements=disagreements,
                )
            )
        except Exception as exc:  # noqa: BLE001 -- same reasoning as run_eval()
            comparison.results.append(
                JudgeComparisonResult(
                    query=query, qwen_verified=0, qwen_unverified=0, qwen_unchecked=0,
                    judge_verified=0, judge_unverified=0, judge_unchecked=0,
                    agreements=0, disagreements=0, error=str(exc),
                )
            )
    return comparison


def format_judge_comparison(comparison: JudgeComparisonReport) -> str:
    lines = ["Per-query Qwen vs. judge comparison:"]
    for r in comparison.results:
        if r.error is not None:
            lines.append(f"  ERROR  {r.query!r}: {r.error}")
        else:
            lines.append(
                f"  qwen(v={r.qwen_verified},u={r.qwen_unverified},unchecked={r.qwen_unchecked}) "
                f"judge(v={r.judge_verified},u={r.judge_unverified},unchecked={r.judge_unchecked}) "
                f"agree={r.agreements} disagree={r.disagreements}  {r.query!r}"
            )
    lines.append("")
    qa = comparison.qwen_accuracy
    ja = comparison.judge_accuracy
    ar = comparison.agreement_rate
    lines.append(f"Qwen3-4B self-judged accuracy:  {f'{qa:.1%}' if qa is not None else 'N/A'}")
    lines.append(f"Llama-3.1-8B judge accuracy:    {f'{ja:.1%}' if ja is not None else 'N/A'}")
    lines.append(f"Agreement rate:                 {f'{ar:.1%}' if ar is not None else 'N/A'}")
    total_qwen_unchecked = sum(r.qwen_unchecked for r in comparison.results if r.error is None)
    if total_qwen_unchecked:
        lines.append(
            f"NOTE: Qwen's own citation_verifier call left {total_qwen_unchecked} "
            f"citation(s) unchecked across this run (parse failure -- "
            f"verify_citations() fails open rather than guessing, per "
            f"citation_verifier.py's own docstring). Those unchecked "
            f"citations are excluded from Qwen's own accuracy figure "
            f"above but WERE independently resolved by the judge where "
            f"possible -- a gap this size between the two models' "
            f"unchecked counts is itself a reliability signal worth "
            f"tracking over time, not just noise."
        )

    # Disagreement concentration -- the aggregate agreement rate alone
    # can read as "uncertainty spread evenly across queries" when the
    # real pattern is a handful of queries accounting for ALL the
    # disagreement and everything else agreeing perfectly. That
    # distinction is the actionable part; see D-051 follow-up.
    disagreeing = comparison.disagreeing_queries
    if disagreeing:
        lines.append("")
        lines.append(
            f"Disagreement concentration: {len(disagreeing)}/"
            f"{sum(1 for r in comparison.results if r.error is None)} queries "
            f"account for all {comparison.total_disagreements} disagreement(s):"
        )
        for r in disagreeing:
            lean = "Qwen more lenient" if r.qwen_verified > r.judge_verified else (
                "judge more lenient" if r.judge_verified > r.qwen_verified else "mixed"
            )
            lines.append(
                f"  {r.query!r}: qwen(v={r.qwen_verified},u={r.qwen_unverified}) "
                f"judge(v={r.judge_verified},u={r.judge_unverified}) -- {lean}"
            )

    qwen_only_zero = comparison.qwen_only_zero_queries
    if qwen_only_zero:
        lines.append("")
        lines.append(
            f"Qwen-side parse failures, resolved by the judge "
            f"({len(qwen_only_zero)} quer{'y' if len(qwen_only_zero) == 1 else 'ies'}):"
        )
        for r in qwen_only_zero:
            lines.append(f"  {r.query!r}")

    all_unsupported = comparison.perfect_agreement_all_unsupported_queries
    if all_unsupported:
        lines.append("")
        lines.append(
            f"Both models agree citations are unsupported (retrieval/"
            f"grounding signal, not a judge-disagreement signal) "
            f"({len(all_unsupported)} quer{'y' if len(all_unsupported) == 1 else 'ies'}):"
        )
        for r in all_unsupported:
            lines.append(f"  {r.query!r}")

    return "\n".join(lines)


def append_judge_comparison_to_log(comparison: JudgeComparisonReport, hardware_note: str = "(unspecified)") -> None:
    """Same append-only, never-overwrite pattern as append_to_log() --
    a separate section within the same docs/eval_log.md so both the
    single-judge accuracy history and the dual-judge comparison history
    live in one place, per D-049."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    qa, ja, ar = comparison.qwen_accuracy, comparison.judge_accuracy, comparison.agreement_rate
    total_qwen_unchecked = sum(r.qwen_unchecked for r in comparison.results if r.error is None)
    total_judge_unchecked = sum(r.judge_unchecked for r in comparison.results if r.error is None)
    entry = (
        f"\n### {timestamp} (Qwen vs. Llama-3.1-8B judge comparison, D-049)\n"
        f"**Hardware:** {hardware_note}\n"
        f"**Queries run:** {len(comparison.results)} "
        f"({sum(1 for r in comparison.results if r.error)} errored)\n"
        f"**Qwen3-4B self-judged accuracy:** {f'{qa:.1%}' if qa is not None else 'N/A'} "
        f"({total_qwen_unchecked} citation(s) left unchecked by Qwen's own call)\n"
        f"**Llama-3.1-8B judge accuracy:** {f'{ja:.1%}' if ja is not None else 'N/A'} "
        f"({total_judge_unchecked} citation(s) left unchecked by the judge)\n"
        f"**Agreement rate:** {f'{ar:.1%}' if ar is not None else 'N/A'} "
        f"({comparison.total_agreements} agree / {comparison.total_disagreements} disagree)\n"
    )
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def main_with_judge() -> int:
    """Entry point for --with-judge: loads Qwen3-4B, runs phase A for
    every query, EXPLICITLY frees it, then loads the judge for phase B.
    Never both models resident at once -- see judge_model.py's module
    docstring and D-049."""
    import gc

    from core.llm_backend import get_model, ModelNotFoundError
    from judge_model import JudgeModel, JudgeModelNotFoundError

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"citation_accuracy_eval --with-judge: {exc}", file=sys.stderr)
        return 2

    queries = load_queries()

    # Phase A: Qwen3-4B generates + self-judges, exactly as the normal
    # agentic path always has. run_eval_with_judge does both phase A
    # (via run_agentic) and phase B (via judge_model) internally, but
    # we free `model` BEFORE constructing the judge, which is the part
    # that actually needs sequencing -- see below.
    #
    # NOTE: run_eval_with_judge takes both models as arguments, so we
    # need Qwen resident for phase A's run_agentic() calls and the
    # judge resident for phase B's verify_citations() calls -- the
    # cleanest way to guarantee they're never BOTH resident without
    # restructuring run_eval_with_judge into two separate passes is to
    # do phase A here directly, free Qwen, load the judge, then run
    # phase B. That's what the block below does, rather than calling
    # run_eval_with_judge() as one call with both models passed at
    # once (which would require Qwen to still be in memory when the
    # judge loads).
    from rag.graph import run_agentic as _run_agentic
    from verification.citation_verifier import summarize as _summarize

    phase_a_results = []
    for i, query in enumerate(queries, 1):
        print(f"[phase A: Qwen3-4B, {i}/{len(queries)}] {query}", file=sys.stderr)
        try:
            final_state = _run_agentic(
                query, model, enable_self_consistency=False,
                debug_report=lambda msg: print(f"  [debug] {msg}", file=sys.stderr),
            )
            phase_a_results.append(
                {
                    "query": query,
                    "chunks": final_state.get("retrieved_chunks", []),
                    "citations": final_state.get("citations", []),
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            phase_a_results.append({"query": query, "chunks": [], "citations": [], "error": str(exc)})

    del model
    gc.collect()
    print("Freed Qwen3-4B, loading judge model...", file=sys.stderr)

    try:
        judge_model = JudgeModel()
    except JudgeModelNotFoundError as exc:
        print(f"citation_accuracy_eval --with-judge: {exc}", file=sys.stderr)
        return 2

    from verification.citation_verifier import verify_citations

    comparison = JudgeComparisonReport()
    for i, r in enumerate(phase_a_results, 1):
        print(f"[phase B: judge, {i}/{len(phase_a_results)}] {r['query']}", file=sys.stderr)
        if r["error"] is not None:
            comparison.results.append(
                JudgeComparisonResult(
                    query=r["query"], qwen_verified=0, qwen_unverified=0, qwen_unchecked=0,
                    judge_verified=0, judge_unverified=0, judge_unchecked=0,
                    agreements=0, disagreements=0, error=r["error"],
                )
            )
            continue
        try:
            qwen_verified, qwen_unverified, qwen_unchecked = _summarize(r["citations"])
            judge_input = [{**c, "verified": None} for c in r["citations"]]
            judge_citations = verify_citations(
                judge_input, r["chunks"], judge_model,
                debug_report=lambda msg: print(f"  [debug] {msg}", file=sys.stderr),
            )
            judge_verified, judge_unverified, judge_unchecked = _summarize(judge_citations)

            agreements = disagreements = 0
            for qc, jc in zip(r["citations"], judge_citations):
                qv, jv = qc.get("verified"), jc.get("verified")
                if qv is None or jv is None:
                    continue
                agreements += qv == jv
                disagreements += qv != jv

            comparison.results.append(
                JudgeComparisonResult(
                    query=r["query"], qwen_verified=qwen_verified, qwen_unverified=qwen_unverified,
                    qwen_unchecked=qwen_unchecked, judge_verified=judge_verified,
                    judge_unverified=judge_unverified, judge_unchecked=judge_unchecked,
                    agreements=agreements, disagreements=disagreements,
                )
            )
        except Exception as exc:  # noqa: BLE001
            comparison.results.append(
                JudgeComparisonResult(
                    query=r["query"], qwen_verified=0, qwen_unverified=0, qwen_unchecked=0,
                    judge_verified=0, judge_unverified=0, judge_unchecked=0,
                    agreements=0, disagreements=0, error=str(exc),
                )
            )

    print(format_judge_comparison(comparison))
    append_judge_comparison_to_log(comparison)
    print(f"\nLogged to {_LOG_PATH}")
    return 0


def main() -> int:
    from core.llm_backend import get_model, ModelNotFoundError

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"citation_accuracy_eval: {exc}", file=sys.stderr)
        return 2

    queries = load_queries()
    eval_report = run_eval(
        queries, model,
        report=lambda msg: print(msg, file=sys.stderr),
        debug_report=lambda msg: print(f"  [debug] {msg}", file=sys.stderr),
    )
    print(format_report(eval_report))
    append_to_log(eval_report)
    print(f"\nLogged to {_LOG_PATH}")
    return 0


if __name__ == "__main__":
    if "--with-judge" in sys.argv:
        sys.exit(main_with_judge())
    sys.exit(main())
