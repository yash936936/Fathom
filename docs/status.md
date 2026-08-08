# status.md — Live Status Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Update this file at the end of EVERY task, every run, no exceptions**
> (per `workflow.md` §3). Newest entry at the top. Never delete history.

---

## Current state
- **Active phase:** Phase 1/2 — blocked on unexplained latency, not on
  correctness
- **Phase status:** Correctness confirmed for both phases: model loads
  and generates coherent output; `classify_domain()` scored 5/5 on a
  real-model smoke test (0.95–0.99 confidence), including correctly
  catching an injection-style query. BUT: generation speed measured at
  ~0.9 tok/s (68.2s model load, 46.6s for a ~40-token reply), roughly
  10-20x slower than expected for this hardware profile with full AVX512
  + weight-repack acceleration confirmed active (see decisions.md D-016 —
  D-015's "missing SIMD" hypothesis was tested and disproven). This fails
  `trd.md`'s latency targets outright, not marginally.
- **Next phase:** Phase 3 — Tools & hybrid retrieval. NOT started.
  Deliberately held per D-015/D-016: building retrieval/RAG on top of an
  unexplained ~20x slowdown means every later phase inherits and
  compounds an undiagnosed problem.
- **Blockers:** root cause of the slowdown is unidentified. User handed
  three diagnostic steps to try: (1) close VS Code/other CPU-competing
  processes, test from a plain terminal, (2) confirm Windows power plan
  isn't throttling (Balanced/Power saver/on-battery), (3) if neither
  resolves it, test Windows Defender real-time-scan interference with
  the mmap'd model file. Waiting on results before Phase 3 starts, or an
  explicit user override to proceed anyway with the risk acknowledged.

---

## Log (newest first)

### Entry 005
**Phase:** 1 (troubleshooting) + 2 (wrap-up)
**Action taken:** Helped debug the user's real-machine setup: (1) `curl`
failed because `~/.fathom/models/` didn't exist yet (curl doesn't
auto-create parent dirs) -- fixed with `mkdir -p` first; (2) a Git Bash
`~/.bash_profile` auto-creation notice was correctly identified as
harmless, not an error. Added `.gitignore` (excludes venv, `*.gguf`/
`models/`, `__pycache__`, build output, OS cruft, `.env`). Wrote
`verify_real_model.py` -- a script for the user to run on their own
machine that (a) loads the real model and times it, proving Phase 1's
exit criteria, and (b) runs `classify_domain()` against 5 real test
queries with known expected answers, closing the D-014 follow-up
(stub-only verification was not sufficient on its own).
**Decisions logged this run:** none new -- this was execution of
already-decided work (D-008 model-not-bundled, D-014's follow-up
condition), not a new decision point.
**Debug entries logged this run:** none yet -- the curl/bash-profile
issues were user-environment troubleshooting, not bugs in Fathom's own
code, so they don't belong in debug.md's bug-log format. If
`verify_real_model.py`'s output reveals an actual code issue, that gets
logged then.
**Phase 1 exit criteria met?** Still not confirmed -- model file is
downloaded, but no `main.py` or `verify_real_model.py` output has been
reported back yet.
**Phase 2 exit criteria met?** Partially -- stub-based logic verification
done (13/13). Real-model accuracy check (`phases.md` Phase 2's ">=95%
correct routing" target) not yet run.
**Next action for next session:** get `verify_real_model.py` output from
the user, log the actual load time, memory behavior, and domain-gate
accuracy numbers here, then mark Phase 1 and Phase 2 complete (or debug
whatever it surfaces).

### Entry 004
**Phase:** 1
**Action taken:** Wrote `src/core/state.py` (ResearchState TypedDict +
Citation/RetrievedChunk/ConversationTurn types), `src/core/llm_backend.py`
(FathomModel wrapper around llama-cpp-python, lazy singleton, resolves
model path via FATHOM_MODEL_PATH or default cache dir), `src/main.py`
(minimal argparse CLI, Phase 1 scope only), `requirements.txt`. Package
`__init__.py` files added for `core/`, `rag/`, `tools/`, `verification/`,
`memory/`, `installer_support/`.
**Decisions logged this run:** D-012 in `decisions.md` — n_ctx=8192
default, explicit n_gpu_layers=0, lazy llama_cpp import, argparse over
click/typer for Phase 1.
**Debug entries logged this run:** B-001 in `debug.md` — llama-cpp-python
could not be installed/verified end-to-end in this sandbox (source build
timeout; background processes don't persist across tool calls here).
Worked around by verifying everything else: syntax compiles clean, and
the full CLI error path (missing model, missing deps) behaves correctly
without ever needing the real dependency installed.
**Phase 1 exit criteria met?** Partially. Code is written and the parts
verifiable in this sandbox pass. NOT met: "confirm single hardcoded
prompt → completion works end-to-end" and "memory footprint measured and
logged" both require the actual GGUF model loaded, which needs a real
machine with network access to huggingface.co. Do not advance to Phase 2
until this is confirmed — see workflow.md §4.
**Next action for next session:** On a real dev machine: `pip install -r
requirements.txt`, download Qwen3-4B-Instruct-2507 (Q4_K_M GGUF) to
`~/.fathom/models/qwen3-4b-instruct-2507-q4_k_m.gguf` (or set
FATHOM_MODEL_PATH), run `python src/main.py "test query"`, confirm output
and measure actual RSS memory usage. Log the result here, then Phase 1 can
be marked complete and Phase 2 can start.

### Entry 003
**Phase:** 0 (still pre-code — naming/branding decision, not a new phase)
**Action taken:** Named the project **Fathom** (CLI command: `fathom`).
Verified candidate names against PyPI/GitHub before shortlisting (Scout,
Verity, Ledger all rejected on real collisions; Fathom and veriscout both
came back clean; user chose Fathom). Renamed all placeholder references
from `research-cli` to `fathom` in `readme.md`, `context.md`,
`architecture.md`, `phases.md`, `appflow.md`.
**Decisions logged this run:** D-011 in `decisions.md` — full naming
rationale and collision-check trail.
**Debug entries logged this run:** none (still no code).
**Phase 0 exit criteria met?** Still yes — naming is a refinement within
Phase 0, doesn't block Phase 1.
**Next action for next session:** Unchanged — begin Phase 1 per `phases.md`
(`src/core/llm_backend.py` loading the Fathom model, Qwen3-4B-Instruct-2507
GGUF). Also recommend confirming domain/trademark availability for
"fathom" separately before any public launch (not checked in D-011).

### Entry 002
**Phase:** 0 (still pre-code — this is a docs/architecture refinement, not
a new phase)
**Action taken:** Reviewed 12 externally suggested GitHub repos for reusable
logic (per user request). Adopted 3 patterns as logic (not code/dependency):
curator node, retry-cap-with-explicit-caveat, eval metric taxonomy. Updated
`architecture.md` (added `rag/curator.py`, documented 3 new v2 extension
points), `code_logic.md` (§4 curator node + sharpened sufficiency-loop
exhaustion behavior, new §9 external references section), `trd.md` (§7 eval
taxonomy).
**Decisions logged this run:** D-010 in `decisions.md` — full breakdown of
adopted/deferred/rejected repos with rationale for each.
**Debug entries logged this run:** none (still no code).
**Phase 0 exit criteria met?** Still yes — this was a refinement within
Phase 0, not a new phase. `architecture.md` and `code_logic.md` remain
internally consistent after the edit (curator node added to both the file
tree, the component table, and the graph pseudocode).
**Next action for next session:** Unchanged — begin Phase 1 per `phases.md`.

### Entry 001
**Phase:** 0
**Action taken:** Created full documentation scaffold: `context.md` (root)
and all files in `docs/` — `prd.md`, `trd.md`, `architecture.md`,
`phases.md`, `decisions.md`, `debug.md`, `code_logic.md`, `appflow.md`,
`workflow.md`, `readme.md`, `status.md` (this file).
**Decisions logged this run:** D-001 through D-009, all in `decisions.md`
(model choice, no fine-tuning in v1, no gateway layer, packaging approach,
model-download-not-bundled, domain-gate-as-classifier, multi-agent deferred,
verification cost gating, training-compute exception).
**Debug entries logged this run:** none (no code yet).
**Phase 0 exit criteria met?** Yes — doc scaffold complete, cross-referenced,
routing table in `context.md` verified against actual file list.
**Next action for next session:** Begin Phase 1 per `phases.md`. Start with
`src/core/llm_backend.py` — load Qwen3-4B-Instruct-2507 GGUF via
llama-cpp-python, confirm memory footprint stays under budget (`trd.md` §1),
log the actual measured footprint here once available.

---
**Return to `/context.md` for next steps.**
