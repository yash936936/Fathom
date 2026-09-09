"""
tests/eval/watchlist_eval.py — fast, targeted re-run harness.

`golden_set_eval.py` runs all 50 entries in `golden_set.jsonl` every
time -- correct for an official Phase 10 exit-criteria run (prd.md
§5's off-domain-refusal threshold is measured against the full set),
but slow to re-run repeatedly while iterating on one specific fix. This
script reuses `golden_set_eval.py`'s real machinery (same `run_query`
front door, same `_classify_result` refusal-type detection, same
report formatting) against a small, hand-picked, EDITABLE subset in
`watchlist.jsonl` instead.

**This is a diagnostic tool, not a replacement for the real exit-
criteria run.** Its rates are not comparable to `eval_log.md`'s
50-entry-run percentages (different n, different composition) and are
logged to a SEPARATE file (`tests/eval/watchlist_log.md`) specifically
so they never get mixed into the historical trend log that
`docs/eval_log.md` exists to track. Before tagging a release, run the
full `golden_set_eval.py` -- this script is for the sessions in
between.

Current watchlist (10 entries), picked for D-084/D-085 (docs/
decisions.md): the 6 false-premise queries that showed the exact
`confidence=0.0`-with-a-confident-reason pattern D-085's prompt fix
targets (Wikipedia, Python, 10%-brain, Amazon, UN, Tesla), 2
false-premise controls that were ALREADY caught correctly before the
fix (Eiffel, JWST) -- to catch a regression if the prompt change
somehow makes a previously-working case worse, one `answerable` control
(transistor) to catch a false-positive regression, and one `off_domain`
control (Python-linked-list) to catch an input_rail/domain_gate
regression. Edit `watchlist.jsonl` directly to change what's tracked --
this file's logic doesn't care what's in it, same `load_golden_set`
loader and category validation as the full set.

NOTE on a discrepancy found while building this list, not yet
resolved: the Wikipedia and Amazon entries are tagged
`domain_gate_refused` in `golden_set.jsonl` (their originally-observed
subtype), but the most recent real transcript (the run analyzed in
D-084) shows BOTH reaching the evidence-based check with
`domain_ok=True` -- i.e. NOT refused by domain_gate that run. Carried
through unchanged here rather than silently re-tagged, since this
project's own practice (D-068) is to tag subtype from observed
behavior, not guess it -- the next watchlist run's `--debug` output
will show directly which mechanism actually handles each one now.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from golden_set_eval import (  # noqa: E402
    format_report,
    load_golden_set,
    run_golden_set,
)

_WATCHLIST_PATH = _THIS_DIR / "watchlist.jsonl"
_LOG_PATH = _THIS_DIR / "watchlist_log.md"


def append_to_watchlist_log(golden_report, hardware_note: str = "(unspecified)") -> None:
    """Deliberately separate from golden_set_eval.append_to_log() --
    writes to watchlist_log.md, never docs/eval_log.md. Keeps the same
    per-run shape (timestamp, entries run, rates) so a human comparing
    the two logs isn't confused by a format mismatch, but a distinct
    header makes it unmistakable which kind of run produced each entry.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    odr = golden_report.off_domain_refusal_rate
    fpr = golden_report.false_premise_catch_rate
    afp = golden_report.answerable_false_positive_refusal_rate
    entry = (
        f"\n### {timestamp} (Watchlist eval, {len(golden_report.results)} entries -- "
        f"NOT the full 50-entry golden set, not comparable to eval_log.md rates)\n"
        f"**Hardware:** {hardware_note}\n"
        f"**Off-domain refusal rate (n={len(golden_report.by_category('off_domain'))}):** "
        f"{f'{odr:.1%}' if odr is not None else 'N/A'}\n"
        f"**False-premise catch rate (n={len(golden_report.by_category('false_premise'))}):** "
        f"{f'{fpr:.1%}' if fpr is not None else 'N/A'}\n"
        f"**Answerable false-positive refusal rate (n={len(golden_report.by_category('answerable'))}):** "
        f"{f'{afp:.1%}' if afp is not None else 'N/A'}\n"
    )
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def main() -> int:
    from core.llm_backend import get_model, ModelNotFoundError

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"watchlist_eval: {exc}", file=sys.stderr)
        return 2

    debug_report = (
        (lambda msg: print(f"  [debug] {msg}", file=sys.stderr))
        if "--debug" in sys.argv[1:] else None
    )

    entries = load_golden_set(_WATCHLIST_PATH)
    golden_report = run_golden_set(
        entries, model,
        report=lambda msg: print(msg, file=sys.stderr),
        debug_report=debug_report,
    )
    print(format_report(golden_report))
    append_to_watchlist_log(golden_report)
    print(f"\nLogged to {_LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
