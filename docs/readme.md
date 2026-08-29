# Fathom

> Redirect: after reading, return to `/context.md` for routing.
> This file is copied/adapted to the repo root `README.md` at release points.
> Update it as phases complete (per `workflow.md` §3.5) — it should always
> reflect *actually working* capability, not planned capability.

## Status: pre-v1.0 — Windows, real-hardware confirmed, tag pending D-065

Core pipeline (model, domain gate, retrieval, adaptive routing, agentic
loop, citation verification, multi-turn memory) is built and confirmed
working end-to-end on real Windows hardware. **This release is Windows
only** — macOS is blocked on hardware access, Linux works when run
directly but isn't yet packaged as an installer. Both are deferred to
a follow-up release, not dropped. See `docs/decisions.md` D-064.

**No v1.0 tag has been cut yet.** A real-hardware run just surfaced a
genuine metric-stability issue (false-premise catch rate varies
83.3%/50.0% between identical runs — `decisions.md` D-065); the tag is
deliberately being held until that's either fixed or honestly
documented as a range, rather than shipping on a single favorable run.

## What this is
A small, offline-first, open-source CLI research assistant. Ask a research
question, get an answer grounded in live retrieval with verifiable
citations — no GPU, no API key.

- **Model:** Qwen3-4B-Instruct-2507 (Apache 2.0, GGUF, ~2.5GB)
- **Scope:** research questions only — not a coding or general chat tool
- **Runs on:** CPU only, <6GB RAM
- **Install:** single Windows installer; model downloads automatically
  during setup

## Installation (Windows)
1. Download and run `fathom-setup.exe`.
2. The installer places the binary and, on first run, downloads the
   ~2.5GB model with progress and a checksum verification step.
3. Once installed, run `fathom "your question"` from anywhere.

Uninstall via the Start Menu's "Uninstall Fathom" shortcut (also
present alongside the "Fathom" launch shortcut).

## Usage
```
fathom "your research question"

--mode {quick,deep}   quick = fastest available (heuristic domain
                       check, fast path only, short answer) -- not a
                       guaranteed time limit. deep = full accuracy
                       (LLM domain check, adaptive routing). Default: deep.
--chat                Start an interactive multi-turn session. Follow-up
                       questions can reference prior answers. Type
                       'exit'/'quit' or Ctrl+C/Ctrl+D to leave.
--verbose, -v          After the answer, print flags and elapsed time.
--debug                Print per-tool retrieval/verification diagnostics
                       to stderr as the query runs.
--max-tokens N         Max tokens for the final answer.
--top-k N              Max retrieved chunks kept after reranking
                       (default: 8).
--self-consistency     Enable an extra resample-and-compare pass on the
                       agentic path (off by default -- adds real
                       latency; see decisions.md D-045/D-046).
--ensure-model         Download the model if missing, then exit. Used
                       by the installer; also useful standalone.
```

Every answer carries per-claim citations to its retrieved sources.
Off-topic (non-research) questions are refused before any retrieval
happens. Questions built on a false premise are flagged rather than
answered as if the premise were true.

## Real measured numbers (Windows, `docs/eval_log.md`)
- **Off-domain refusal rate:** 100.0% (`prd.md` threshold: >=95%),
  stable across 4 real runs.
- **Answerable false-positive refusal rate:** 0.0% (ideal), stable
  across the 2 most recent real runs (was 10.0% on an earlier run —
  improving, not yet enough runs to call it fully settled).
- **False-premise catch rate:** **50.0%–83.3%, NOT yet stable** —
  two identical back-to-back real runs produced different numbers.
  Root-caused to a non-deterministic generation step (see
  `decisions.md` D-065); a fix is planned but not yet applied. Treat
  this figure as a real, open weak point, not a settled number — v1.0
  tagging is deliberately being held until this either stabilizes or
  is reported as an honest range with a documented fix in progress.
- **Per-claim citation accuracy:** 57.1% (last SINGLE-JUDGE measurement
  on record; predates the citation_verifier fix in D-063). A separate
  Qwen-vs-independent-judge comparison run post-fix showed the
  verifier's `unchecked` rate drop substantially (12 → 3 citations),
  a positive but not yet a re-measurement of this specific number —
  a plain (non-`--with-judge`) re-run is still owed for that.

These are real, tracked, and openly still-moving — not a final or
stable state. See `docs/eval_log.md` for the full run-by-run history
and `docs/status.md`/`docs/decisions.md` D-065 for what's currently
open. **v1.0 has not been tagged yet** — see "Known limitations" below.

## Known limitations
- Windows only in this release (macOS/Linux deferred — D-064).
- **False-premise detection is not yet reliable** — see the range
  above. Don't treat a "this seems answerable" response as confirmation
  the premise is real; verify anything surprising.
- Latency is real, not fast: deep-mode queries typically run in the
  low hundreds of seconds on modest CPU hardware (see `trd.md` §6),
  a deliberate accuracy-over-speed tradeoff, not an unmeasured gap.
  `--mode quick` trades some accuracy for a faster path.
- Citation accuracy (above) is real but not yet high enough to treat
  every citation as ground truth — verify anything load-bearing.

## Architecture
See `docs/architecture.md` for the full system design, `docs/prd.md` for
scope/goals, `docs/trd.md` for technical constraints.

## Contributing / development
See `docs/workflow.md` for the working process and `docs/phases.md` for the
current build plan.

## License
*(To be finalized — model is Apache 2.0; project license tracked as a
decision pending in `docs/decisions.md`.)*

---
**Return to `/context.md` for next steps.**
