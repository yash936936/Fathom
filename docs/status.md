# status.md — Live Status Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Update this file at the end of EVERY task, every run, no exceptions**
> (per `workflow.md` §3). Newest entry at the top. Never delete history.

---

## Current state
- **Active phase:** UX feature (quick/deep modes + spinner) — B-008
  closed for real; a bigger open question surfaced (latency variance)
- **Feature status:** All three modes confirmed working on real
  hardware across multiple runs. B-008 (truncation) CLOSED — re-tested
  twice more, both answers ended cleanly, no truncation. Full
  regression: 87/87.
- **Open, more important than B-008 was:** D-029 — the same simple
  query, same mode, same machine, back-to-back runs measured 139.0s,
  141.4s, and then 3277.0s (54.6 min) with nothing externally different
  (confirmed directly with the user: no sleep, no other heavy programs,
  nothing noticed). All prior latency figures (D-022's 375.7s baseline,
  D-024-026's ~250-450s range) should now be read as samples from a
  wide, poorly-understood distribution, not stable numbers. `trd.md` §6
  updated to state this honestly. Root cause NOT identified — leading
  unconfirmed candidate is intermittent Defender/antivirus interference
  (raised as a hypothesis back in D-016, never actually tested).
- **Still outstanding, unrelated:** B-007's Phase 5 retry-refinement fix
  (fusion-vs-fission comparison query) still needs its own real-hardware
  confirmation — untouched since the UX feature work started.
- **Latency:** no longer treated as a stable ~375s baseline — see D-029.
  Quick mode's actual speed also still unmeasured precisely (didn't
  time it in the two confirmation runs), though it completed without
  the earlier truncation issue.
- **Next phase:** Phase 6 — Hallucination/verification layer, OR
  finishing Phase 5's real-hardware confirmation first. Should not
  start until BOTH the Phase 5 fix chain AND this UX feature are
  confirmed on real hardware — the
  prior confirmation was of buggy behavior that happened to produce a
  correct-looking result.
- **Blockers:** real-machine verification of the fixed `run_agentic()`
  retrieval) has not been run yet — only stub-based graph execution is
  confirmed so far.

---

## Log (newest first)

### Entry 015
**Phase:** UX feature, refinement
**Action taken:** simplified `--verbose` per direct user request — it
now uses the identical spinner UI as default mode during processing,
differing only in an added flags+timing footer after the same clean
output. Also resolved a latent design conflict (spinner + live streaming
writing to the terminal simultaneously) that the old verbose design
would have hit.
**Decisions logged this run:** D-030.
**Debug entries logged this run:** none — clean refactor, 87/87 on
first pass.
**Feature exit criteria met?** Code-complete, unit-verified, help text
and error paths manually re-checked. NOT yet verified on real hardware.
**Next action for next session:** confirm `--verbose` on real hardware
shows the spinner (not stage-by-stage lines) followed by the flags/
timing footer. Still separately outstanding: B-007's Phase 5 fix
real-hardware confirmation, and the D-029 latency-variance investigation
whenever it next recurs.

### Entry 014
**Phase:** UX feature, second real-hardware confirmation
**Action taken:** re-ran quick mode twice more — both times the
truncation fix held, answers ended on complete sentences. Closed B-008.
While confirming this, noticed a `--verbose` run of the identical query
took 3277.0s vs. 139-141s for the same query moments earlier. Asked the
user directly whether anything external explained it (sleep, other
programs) — answer was no, nothing unusual noticed. Rather than treat
this as a one-off to ignore, documented it as a real, unexplained
variance finding and revised `trd.md` §6 to stop presenting D-022's
375.7s as a stable baseline.
**Decisions logged this run:** D-029 — full variance finding, candidate
causes (none confirmed), and a concrete low-effort next step (check
Task Manager CPU/Defender activity next time it recurs) rather than
guessing further without evidence.
**Debug entries logged this run:** B-008 marked closed in `debug.md`.
**Feature exit criteria met?** Yes for the mode/UI feature itself
(truncation fix confirmed twice, spinner/quiet-mode contract already
confirmed in Entry 013). The latency-variance question is now its own
open item, separate from the feature being "done."
**Next action for next session:** two independent open items, either
order: (1) B-007's Phase 5 retry-refinement real-hardware confirmation
(fusion-vs-fission query, untouched since Entry 012), (2) if a future
slow run happens again, capture Task Manager's Performance tab during
it (CPU%, and specifically whether an antivirus/Defender process shows
sustained activity) — first real evidence toward the D-029 variance
question, rather than another unexplained data point.

### Entry 013
**Phase:** UX feature, first real-hardware verification
**Action taken:** ran all three modes for real (default quiet, quick,
verbose). Quiet mode's output contract confirmed correct. Caught a real
bug myself in quick mode's output (mid-word truncation) rather than
waiting for it to be reported — fixed with `_smooth_truncation()` in
`rag/synthesis.py`, verified against the exact real truncated text from
the run.
**Decisions logged this run:** D-028 — full finding writeup (positive
confirmation + the truncation bug + fix + scoping note about verbose
mode's live streaming not being retroactively fixable).
**Debug entries logged this run:** B-008 — root cause + fix.
**Feature exit criteria met?** Mostly — core mode/spinner behavior
confirmed on real hardware. The truncation fix itself hasn't had its
own second real-run confirmation yet. 87/87 regression sweep.
**Next action for next session:** re-run `--mode quick` once more to
confirm the truncation fix actually produces a clean sentence ending in
practice, not just against the replayed fixture text. Separately, still
owed from Entry 011: B-007's Phase 5 retry-refinement fix real-hardware
confirmation (the fusion-vs-fission comparison query) — this hasn't been
revisited since this UX feature work started.

### Entry 012
**Phase:** UX feature (quick/deep modes, spinner, verbose flag)
**Action taken:** built the mode/UI feature requested: `--mode
{quick,deep}`, `--verbose`/`-v`, `core/ui.py`'s `Spinner` +
`make_stage_reporter()`, `core/domain_gate.py`'s new
`quick_domain_check()` heuristic, `rag/graph.py` refactored to take an
injected `report` callback, `main.py` fully rewritten around
`run_query()`. Was explicit with the user that a guaranteed <30s quick
mode isn't achievable on this hardware (measured ~1.7-2 tok/s) rather
than building something that silently doesn't meet its own advertised
number — quick mode instead minimizes every avoidable cost (no
domain-gate LLM call, forced fast path, tight token cap).
**Decisions logged this run:** D-027 — full design + honesty framing
around the <30s claim, spinner/reporter architecture, quiet-mode output
contract (answer + sources only, matching the explicit user spec).
**Debug entries logged this run:** none — clean implementation, 84/84
first-pass regression sweep with zero breakage in existing behavior.
**Feature exit criteria met?** Code-complete and unit/logic verified
(spinner thread lifecycle, reporter wiring, quick-check heuristics, CLI
arg parsing, error paths). NOT verified: an actual real-hardware run in
quick mode or with the spinner visibly rendering — same "write it,
verify what's verifiable locally, then need real confirmation" pattern
as every other feature in this project.
**Next action for next session:** get real-hardware output for (1)
`py src/main.py "<query>" --mode quick` — confirm timing and that the
heuristic domain check behaves sensibly on a real query, (2) default
quiet mode on a normal query — confirm the spinner renders/clears
correctly in an actual terminal (this can behave differently across
terminal emulators in ways a test harness can't catch), (3) `--verbose`
still matches the old pre-this-change behavior exactly. Also still
outstanding from Entry 011: Phase 5's B-007 fix real-hardware
confirmation.

### Entry 011
**Phase:** 5, third bug fix in the same retry-refinement mechanism
**Action taken:** third real-hardware run of the fusion-vs-fission
comparison query showed B-006's fix was safe (no prose sent as queries)
but silently inert — the model returned an empty `search_query` field
despite explicit instruction, so retries were still non-functional
no-ops. Added `_fallback_query_from_gap()`, a bounded, stopword-filtered
keyword extractor used only when the model itself gives nothing usable.
Verified directly against the exact `gap` text from the live run, not a
synthetic fixture.
**Decisions logged this run:** D-026 — names this as the third fix in a
sequence on the same mechanism, explicit that green tests weren't
sufficient confidence at any prior point in this sequence.
**Debug entries logged this run:** B-007 — root cause (prompt
non-compliance, not a code mishandling bug like B-005/B-006) + fix.
**Phase 5 exit criteria met?** Still not fully — same real-hardware
confirmation gap as after every fix in this phase so far. 68/68 full
regression sweep.
**Next action for next session:** re-run the same query one more time.
This time, check whether the answer actually surfaces fission-reactor
content, not just whether the mechanics look right — three fixes in on
the plumbing, the actual research-quality question (does better
retrieval refinement produce a better answer) still hasn't been
confirmed. If it still can't find fission sources even with a real
extracted query, that may be a genuine source-availability limit rather
than a bug — worth distinguishing those two outcomes explicitly.

### Entry 010
**Phase:** 5, second bug fix
**Action taken:** User re-ran the same comparison query with B-005's fix
applied. Mechanics worked (sub_queries genuinely grew, evidence
accumulated) but answer quality got worse — traced to the fix appending
raw prose (the sufficiency `gap` explanation) as a literal search query,
returning near-random results. Fixed by splitting
`rag/sufficiency.py`'s output schema into `gap` (prose, user-facing
only) and a new `search_query` field (short, validated, the only thing
used for retry re-retrieval). Added a structural 8-word-max rejection
as a backstop, not just a better prompt.
**Decisions logged this run:** D-025 — names the pattern behind both
B-005 and B-006 (conflating human-readable explanation fields with
machine-usable input) rather than treating them as unrelated one-offs.
**Debug entries logged this run:** B-006 — full root cause + fix.
**Phase 5 exit criteria met?** Still not fully. Two bugs fixed, 67/67
regression passing, but the B-006 fix itself has NOT been run on real
hardware yet — same gap as after B-005's fix, which is exactly what
surfaced B-006 in the first place. Don't skip the real-hardware
confirmation step again.
**Next action for next session:** re-run the same fusion-vs-fission
comparison query once more. Specifically check that any new sub_queries
printed in the "Retrieving evidence" stage output look like real search
terms (a few words), not sentences — that's the direct, visible signal
the B-006 fix is working before even looking at the final answer.

### Entry 009
**Phase:** 5, bug fix
**Action taken:** User's first real agentic-path run succeeded
end-to-end (444.1s) with correct, honest behavior on the surface. Close
inspection of the run revealed a real design gap: the retry loop wasn't
actually refining its search or accumulating evidence — flagged directly
rather than accepting the run as a clean pass just because tests were
green and the output looked reasonable. Fixed both the substantive bug
(`rag/graph.py`: accumulate evidence, refine sub_queries with the
sufficiency gap on retry) and a cosmetic duplicate print in `main.py`.
Renamed `retriever_hybrid._dedupe` to public `dedupe` for cross-module
reuse. Added a new regression test in `test_phase5_graph.py` that would
have failed against the pre-fix code.
**Decisions logged this run:** D-024 — real-run finding + why a
non-refining retry loop matters more here than a typical bug, given the
accepted per-call cost from D-022.
**Debug entries logged this run:** B-005 — full root-cause writeup.
**Phase 5 exit criteria met?** Still not fully — the FIXED code has not
been run on real hardware yet. Only the buggy version has real-world
confirmation. Full regression sweep post-fix: 65/65 across all 5 test
files.
**Next action for next session:** re-run the same fusion-vs-fission
style comparison query (or a similar multi-part one) on real hardware
with the fixed code, and specifically check whether the second/third
retrieval attempt's sub_queries actually differ from the first (visible
in principle by what gets retrieved, though not currently printed to
stderr — worth adding if this needs to be visually confirmed rather than
inferred from the final answer's content).

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
