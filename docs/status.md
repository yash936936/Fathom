# status.md — Live Status Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Update this file at the end of EVERY task, every run, no exceptions**
> (per `workflow.md` §3). Newest entry at the top. Never delete history.

---

## Current state
- **Active phase:** Phase 1 — Core model backend
- **Phase status:** In progress — code written and structurally verified;
  full model-load/generation verification blocked on sandbox limitations
  (see debug.md B-001). Not yet marked complete — needs verification on
  a real dev machine before advancing to Phase 2.
- **Next phase:** Phase 2 — Guardrail & domain gate (blocked until Phase 1
  exit criteria are actually confirmed, per workflow.md §4 phase
  transition rule)
- **Blockers:** Phase 1 exit criteria (`phases.md`) require measuring
  actual memory footprint with the real model loaded — not possible in
  this sandbox (no network path to huggingface.co, and
  llama-cpp-python's source build exceeds sandbox time limits). Needs a
  real machine.

---

## Log (newest first)

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
