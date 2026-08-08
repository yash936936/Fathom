# status.md — Live Status Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Update this file at the end of EVERY task, every run, no exceptions**
> (per `workflow.md` §3). Newest entry at the top. Never delete history.

---

## Current state
- **Active phase:** Phase 5 — Agentic path (LangGraph)
- **Phase status:** Phase 4 is now FULLY CONFIRMED — real end-to-end run
  succeeded (375.7s, correct grounded answer with resolving citations,
  see decisions.md D-022). Latency target REVISED (not abandoned) in
  `trd.md` §6 per D-022 — Fathom is scoped as a research tool tolerant of
  multi-minute answers, not a chat tool. Phase 5 code written:
  `rag/planner.py`, `rag/curator.py`, `rag/sufficiency.py`, `rag/graph.py`
  (LangGraph state machine), `main.py` wired to call `run_agentic()` for
  complex queries. 13/13 unit-logic checks + 9/9 full-graph-execution
  checks passing (`test_phase5_manual.py`, `test_phase5_graph.py`) —
  the graph checks are the strongest verification yet, since they run
  the actual compiled LangGraph state machine including a genuinely
  cycling, cap-respecting retry loop, not just isolated function logic.
- **Latency (accepted per D-022, compounding as expected in Phase 5):**
  agentic path chains planner + up to 3 retrieval/sufficiency round
  trips + synthesis — several times the 375.7s fast-path baseline for a
  complex query. This is the expected, accepted consequence of D-022's
  choice, not a new surprise.
- **UX gap noted, not yet fixed:** agentic path has stage-progress
  printing (D-023) but not full token streaming during synthesis like
  the fast path has (D-021) — flagged, not silently left out.
- **Next phase:** Phase 6 — Hallucination/verification layer. Should not
  start until Phase 5's real-model + real-network agentic run is
  confirmed on real hardware.
- **Blockers:** real-machine verification of `run_agentic()` end-to-end
  (a real complex/multi-part query, with the real model and real
  retrieval) has not been run yet — only stub-based graph execution is
  confirmed so far.

---

## Log (newest first)

### Entry 008
**Phase:** 4 closure + 5
**Action taken:** Confirmed Phase 4 fully working end-to-end on real
hardware (375.7s, grounded answer, correct citations). Logged the
latency reframe (D-022) and updated `trd.md` §6 to match reality instead
of leaving a contradicted stale target. Built full Phase 5: planner,
curator (finally implementing the D-010-documented node), sufficiency
check with retry cap, and the LangGraph state machine wiring them
together. Wired `main.py`'s complex-query path to actually call
`run_agentic()` instead of printing a placeholder message. Added
stage-progress output inside the graph's nodes for the same UX reason
as D-021.
**Decisions logged this run:** D-022 (latency reframe + Phase 4
closure), D-023 (Phase 5 build, curator-as-heuristic rationale,
MAX_RETRIES=2 rationale, UX gap noted).
**Debug entries logged this run:** none — everything passed on first
implementation this round.
**Phase 5 exit criteria met?** Partially. Strongest verification yet:
13/13 unit-logic checks + 9/9 full-compiled-graph-execution checks,
including a genuinely cycling and cap-respecting retry loop confirmed
via call-count assertions, not just state inspection. NOT verified: the
real model + real network together on an actual complex query — every
test so far uses a scripted stub model.
**Next action for next session:** get a real end-to-end `main.py` run
with a genuinely complex/multi-part query (something that should trigger
the agentic path, e.g. a comparison question) and report the output +
timing, same pattern as every prior phase's closure.

### Entry 007
**Phase:** 4
**Action taken:** Confirmed Phase 3 fully complete (real-hardware network
verification of all 3 tools + full retrieve/rerank pipeline passed —
logged as D-020). Wrote Phase 4: `core/router.py` (heuristic complexity
classifier, no LLM call), `rag/synthesis.py` (citation-forcing generation
shared across fast/agentic paths), rewrote `main.py` to wire the complete
fast-path pipeline end-to-end.
**Decisions logged this run:** D-020 — Phase 3 closure + router-is-
heuristic-not-LLM rationale + explicit flag that the latency problem is
now concrete (fast path = 2 chained LLM calls at ~1.7 tok/s).
**Debug entries logged this run:** none — 17/17 passed on first run.
**Phase 4 exit criteria met?** Partially. Logic verified
(`test_phase4_manual.py`, 17/17). NOT verified: an actual end-to-end
`main.py` run with the real model against a real query — needs the user
to run it and report output/timing.
**Next action for next session:** get real-machine output from `py
src/main.py "some research question"` — this will be the first true
end-to-end confirmation of the whole pipeline, and will also surface the
real per-query latency number the D-015/D-017/D-018 thread has been
tracking. Do not start Phase 5 until this is reported.

### Entry 006
**Phase:** 1/2 wrap-up + Phase 3
**Action taken:** Applied `use_mmap=False` to `llm_backend.py` as a
default (confirmed ~2x generation speedup, real memory tradeoff logged
in D-017). Proceeded to Phase 3 on explicit user override (D-018),
latency gap still open. Wrote all 7 Phase 3 files: `tools/registry.py`,
`web_search.py` (DuckDuckGo HTML), `arxiv_feed.py` (arXiv Atom API),
`news_feed.py` (Google News RSS) — all three no-API-key by design —
`vector_store.py` (BM25-backed curated store), `rag/retriever_hybrid.py`
(fan-out + dedupe), `rag/reranker.py` (BM25-score + recency heuristic).
**Decisions logged this run:** D-017 (mmap tradeoff), D-018 (Phase 3
override with latency risk carried forward), D-019 (BM25-only retrieval/
heuristic reranker instead of dense embeddings/cross-encoder, torch
dependency conflict with trd.md §1).
**Debug entries logged this run:** B-004 — tools weren't self-registering
because nothing imported their modules; fixed via `tools/__init__.py`
importing all four tool modules, so package import triggers
registration.
**Phase 3 exit criteria met?** Partially. Everything testable without
network access passes (11/11 in test_phase3_manual.py). NOT verified:
the three network-calling tools against their real live endpoints —
sandbox can't reach duckduckgo.com/export.arxiv.org/news.google.com.
**Next action for next session:** on a real machine, run
`test_phase3_manual.py` (should still pass, no network needed) AND
manually test `web_search.search("test query")`,
`arxiv_feed.search("test query")`, `news_feed.search("test query")`
directly to confirm the HTML/XML parsing actually works against live
responses — parsers were written against expected formats, not verified
against real ones. Also: circle back to the still-open latency gap
before Phase 5 (agentic loop) makes it worse.

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
