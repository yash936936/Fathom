# status.md — Live Status Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Update this file at the end of EVERY task, every run, no exceptions**
> (per `workflow.md` §3). Newest entry at the top. Never delete history.

---

## Current state
- **ON HOLD:** real-hardware confirmation commands for Phase 6 and the
  macOS/Linux Phase 8 builds were handed off (see D-047's commands),
  but execution is paused at the user's request pending a separate
  discussion of what's next. Nothing below this line should be treated
  as confirmed until the user reports back with actual command output
  -- do not mark Phase 6 or Phase 8 (macOS/Linux) as done based on
  anything in this file alone.
- **Active phase:** Phase 6 — now CODE-COMPLETE. All three planned
  modules exist and are wired: `citation_verifier.py` (previously
  confirmed working), and this session's new
  `verification/answerability.py` and `verification/self_consistency.py`.
  Wired into both the fast path (`main.py`) and agentic path
  (`rag/graph.py`, new `answerability_pre` node + expanded
  `verification` node). See D-045 for full design writeup, including an
  explicit, unresolved cost tradeoff on `self_consistency.py` (adds a
  full extra synthesis call to every agentic query — see below).
- **Phase 6 exit criteria:** the metric-mechanism gap is now CLOSED
  (D-048) — `tests/eval/citation_accuracy_eval.py` establishes and
  tracks per-claim citation accuracy per `trd.md` §7, validated
  end-to-end with a stub model (18/18). What's still open is the DATA:
  no real run has happened yet, so `docs/eval_log.md` has zero real
  entries. That's part of the same "ON HOLD" real-hardware batch below,
  not a separate gap.
- **Windows packaging (Phase 8): still done, unchanged** — real build,
  real hook firing, real standalone execution, real grounded answer
  (D-044). Not touched this session.
- **macOS and Linux (Phase 8): still open** — per D-005, each needs its
  own OS to build on. Not touched this session; still the other
  legitimate next step alongside Phase 6 real-hardware confirmation.
- **Open cost question — RESOLVED this follow-up (D-046):**
  `enable_self_consistency` now defaults to **False** in both
  `build_graph()` and `run_agentic()`. D-045 had left it defaulting to
  `True` while separately flagging the cost as unresolved — that
  wasn't actually a resolution, it just shipped the more expensive
  behavior by default while saying so. Now off until real-hardware
  timing data justifies turning it on.
- **Doc-consistency note — FIXED this follow-up (D-046):**
  `code_logic.md` §3 step 5's citation-check mislabel (flagged, not
  fixed, in D-045) is now corrected — attributes the fast-path
  structural check to `guardrail.output_rail`, not
  `citation_verifier.py`. §7 updated to state the actual sampling
  temperature (0.7) and the new default.
- **Sandbox observation, not a Fathom bug (not logged in debug.md, same
  reasoning as Entry 005's curl/bash-profile note):** this sandbox was
  initially missing `rank_bm25` as an installed dependency. That alone
  wouldn't have been notable, except `unittest.mock.patch("rag.graph.
  retrieve", ...)` silently swallowed the resulting `ModuleNotFoundError`
  and re-raised it as a misleading `AttributeError: module 'rag' has no
  attribute 'graph'` instead — worth remembering if that exact error
  shows up again in a test run, since the real cause is almost
  certainly a missing/broken dependency import inside the patched
  module's import chain, not a genuinely missing attribute.
- **B-018 (this session):** a real bug in
  `verification/self_consistency.py`'s own number-extraction regex
  (`\b` after `%` never matches), found and fixed during this session's
  own test-writing — see `debug.md`. Not a regression in existing code.
- **Regression status:** 180/180 across the full 12-file test suite
  (added `test_phase6_answerability.py`, `test_phase6_self_consistency.py`,
  `test_phase6_graph_wiring.py` this session; updated
  `test_phase5_graph.py`'s scripted-reply sequences for the two new
  model calls now in every agentic graph run). Zero regressions in
  previously-passing behavior.
- **B-011 through B-018 all confirmed/fixed** — B-018 is new this
  session (see above), otherwise unchanged from Entry 027.
- **Latency:** still an open, unresolved-cause variance question — see
  D-029. Not re-investigated this session (though see the new
  self-consistency cost question above, which is related but distinct).
- **Next phase:** two legitimate, independent next steps, same as
  before this session started: (1) real-hardware confirmation of this
  session's Phase 6 work — specifically, run a query that should trigger
  the `answerability_pre` short-circuit, one that shouldn't, and one
  complex enough to exercise `self_consistency` for real, and report
  timing + output for each; (2) macOS and Linux builds for Phase 8.
- **Blockers:** none for the code itself. Real-hardware confirmation
  needs an actual machine with the model downloaded (same as every
  prior phase); macOS/Linux builds need those actual OSes per D-005.

---

## Log (newest first)

### Entry 029
**Phase:** 6, follow-up to Entry 028
**Action taken:** resolved the two items Entry 028 had explicitly left
open rather than fixed: (1) `enable_self_consistency` now defaults to
`False` in `build_graph()`/`run_agentic()` — Entry 028 had flagged the
cost as unresolved while still shipping it on by default, which wasn't
actually a resolution; (2) `code_logic.md` §3 step 5's citation-check
mislabel is now corrected to attribute the fast-path structural check
to `guardrail.output_rail`, and §7 updated to state the real sampling
temperature (0.7) and the new default. Along the way, introduced and
immediately caught a self-inflicted `SyntaxError` in `rag/graph.py`
(a dropped closing `):` from the default-flip edit) — caught by
re-running the regression suite, not by re-reading the diff.
**Decisions logged this run:** D-046.
**Regression status:** 180/180 across the full 12-file suite, confirmed
after fixing the syntax error the same edit introduced.
**Next action for next session:** unchanged from Entry 028 — real-
hardware confirmation of Phase 6 (now with `self_consistency` off by
default, so that confirmation run should explicitly pass
`enable_self_consistency=True` to actually exercise it), and macOS/
Linux builds for Phase 8.

### Entry 028
**Phase:** 6, completion
**Action taken:** built the two remaining Phase 6 modules
(`verification/answerability.py`, `verification/self_consistency.py`)
and wired both into the fast path (`main.py`) and agentic path
(`rag/graph.py`) per `code_logic.md` §3/§4/§6/§7. Added a `temperature`
parameter to `rag/synthesis.generate()` (default unchanged) so
self-consistency could resample without duplicating logic. Updated
`test_phase5_graph.py`'s scripted-reply sequences for the two new model
calls per graph run (and disabled self-consistency in that suite, since
it tests retry-loop logic, not verification). Wrote three new test
files. Along the way, found and fixed a real regex bug in the new
self-consistency module's own fact-extraction (B-018), and diagnosed a
misleading sandbox error (`ModuleNotFoundError` for `rank_bm25` getting
masked by `unittest.mock.patch`'s dotted-path resolution into an
unrelated-looking `AttributeError`) that turned out to be a sandbox
dependency gap, not a code bug.
**Decisions logged this run:** D-045 — full design writeup for both new
modules, the explicit self-consistency cost tradeoff, and a
doc-consistency note about `code_logic.md` §3 step 5.
**Debug entries logged this run:** B-018 — `_NUMBER_PATTERN`'s trailing
`\b` never matched after a `%` sign; fixed by dropping it.
**Phase 6 exit criteria met?** Code-complete, not fully met — see
"Current state" above for what's still outstanding (eval-set metric
tracking, real-hardware confirmation).
**Regression status:** 180/180 across the full 12-file suite, zero
regressions.
**Next action for next session:** real-hardware confirmation of this
session's Phase 6 work (see "Next phase" above for the specific query
types to try), and separately, macOS/Linux builds for Phase 8 whenever
those OSes are available — both remain legitimate, independent next
steps.

### Entry 027
**Phase:** 8, real confirmation (Windows)
**Action taken:** user built the real `main.py` on Windows, confirmed
`hook-llama_cpp.py` fired in the build log, then actually ran the
standalone `.exe` outside any Python venv with a real query — loaded
the model, retrieved real sources, produced a correctly grounded and
cited answer. This is genuine end-to-end confirmation, not just a
successful build.
**Decisions logged this run:** D-044.
**Debug entries logged this run:** none — clean success, no bugs.
**Phase 8 exit criteria met?** For Windows: yes. macOS and Linux remain
untested — each needs building and running on that actual OS per D-005.
**Next action for next session:** macOS and Linux builds, whenever
those OSes are available. Separately: Phase 6 completion
(`answerability.py`, `self_consistency.py`) remains open and
independent of Phase 8's progress.

### Entry 026
**Phase:** 8
**Action taken:** built `build/_common.py`, the three per-OS
`build_<os>.py` scripts, `build/hooks/hook-llama_cpp.py`, and
`build/requirements-build.txt`. Verified what's actually verifiable in
this sandbox: installed PyInstaller (fast), ran a real build against a
stand-in script, confirmed the resulting executable runs standalone,
and confirmed the hook directory doesn't break anything when passed
even without the hooked module being used.
**Decisions logged this run:** D-043 — `--onedir` rationale, exact
scope of what was/wasn't verified.
**Debug entries logged this run:** none — clean build, no bugs found
in the mechanics that were testable.
**Phase 8 exit criteria met?** Partially. Build scripts work
mechanically. NOT met: an actual `main.py` build (needs
llama-cpp-python, untestable here), and no cross-platform testing at
all (sandbox is Linux-only).
**Next action for next session:** on real hardware, per OS: `pip
install -r requirements.txt -r build/requirements-build.txt`, then
`python build/build_<os>.py`, then actually run the resulting
executable with a real query and confirm it works exactly like running
`py src/main.py` from source does. This needs to happen on Windows,
macOS, AND Linux separately per D-005 — start with whichever OS the
user has available first.

### Entry 025
**Phase:** 7 real confirmation; Phase 8 starting
**Action taken:** user ran a real `--chat` session. Worked correctly on
the first try — "that" resolved correctly across turns, retrieval used
only the raw follow-up (no context pollution), all citations resolved
to real sources. Logged as a clean confirmation (D-042), not left
unrecorded just because nothing broke.
**Decisions logged this run:** D-042.
**Debug entries logged this run:** none — no bugs found.
**Next action for next session:** begin Phase 8 (PyInstaller packaging)
per `phases.md` — this entry continues into that work.

### Entry 024
**Phase:** B-017 fixed; Phase 7 built (discovered largely already
implemented from earlier work this session, verified and completed)
**Action taken:** fixed B-017 (comma-in-bracket citations, recurred in
real usage after being deliberately deferred) using the same mechanism
as B-016. Moved to Phase 7 per user request — found `synthesis.py`,
`graph.py`, and `main.py` already had the conversation-context threading
wired in from earlier in this session; wrote the missing piece
(`memory/conversation_buffer.py`) and verified the whole chain end to
end, including confirming by direct code read that domain_gate/router/
retrieval correctly still see only the raw query, never
context-enriched text.
**Decisions logged this run:** D-041 — full Phase 7 design rationale,
specifically why conversation context is synthesis-only.
**Debug entries logged this run:** B-017 closure marker added to the
existing entry.
**Regression status:** 136/136 across all 9 test files.
**Next action for next session:** real-hardware confirmation of
`--chat` mode is the most immediate open item — start a session, ask a
question, then a follow-up that requires resolving a reference ("what
about X instead", "tell me more about the second one") and confirm the
answer actually uses the prior context correctly. Separately still
open: Phase 6 completion (2 of 3 modules unbuilt), Phase 8 packaging,
and the D-029 latency variance investigation whenever it next recurs.

### Entry 023
**Phase:** B-015 confirmed closed; B-016 found and fixed
**Action taken:** re-ran the fusion-vs-fission query. Confirmed B-015
genuinely fixed (no duplicate source_ids). Found a new bug by checking
citation counts against the answer text, not just skimming for
sensible-looking output: 3 cited sources collapsed to 1 in the
verification count. Traced to adjacent citation tags having no text
between them, which the old extraction logic treated as "nothing to
attribute this citation to" and silently dropped. Fixed to reuse the
last real claim text for adjacent tags instead.
**Decisions logged this run:** D-039.
**Debug entries logged this run:** B-015 closed, B-016 new.
**Regression status:** 119/119, zero regressions.
**Next action for next session:** commit this fix (split convention),
then decide whether the still-open comma-in-bracket citation format
gap is worth fixing too, or stays deferred. Also worth a full clean
run without --debug at some point, to confirm the whole pipeline
produces a good user-facing experience end to end, not just that each
individual bug is fixed in isolation.

### Entry 022
**Phase:** B-013/B-014 confirmed closed; B-015 found and fixed
**Action taken:** user re-ran both diagnostic queries. Fine-tuning query
came back fully coherent and well-grounded. Fusion query's tools all
succeeded, but the final Sources list revealed a real, previously
unnoticed bug on inspection — `[news:0]` pointed to two different
articles. Traced to source_id collisions after cross-attempt
accumulation on the agentic path, fixed with a renumbering step.
**Decisions logged this run:** D-038.
**Debug entries logged this run:** B-013/B-014 closed, B-015 new.
**Regression status:** 116/116, zero regressions. New test specifically
designed to exercise the collision (unlike an earlier test whose stub
happened to avoid it by construction).
**Next action for next session:** re-run the fusion-vs-fission query
once more to confirm no more duplicate source_ids appear, and commit
this fix (split convention, not another squash). Separately: the
comma-separated citation regex gap from Entry 021 remains unfixed and
un-prioritized — worth a decision on whether it's worth addressing.

### Entry 021
**Phase:** B-013 confirmed deployed, B-014 found and fixed
**Action taken:** user reported B-013's fix appeared not to work.
Instead of guessing or re-asking for local greps, cloned the actual
live GitHub repo directly. Confirmed B-013 genuinely deployed and
correct — the real problem was one level deeper: arXiv sorting by
recency instead of relevance, undermining even a well-simplified query.
Fixed as B-014. Also caught and corrected my own misreading of a `find`
command that briefly claimed a file was missing when it wasn't.
**Decisions logged this run:** D-037.
**Debug entries logged this run:** B-014.
**Regression status:** 113/113, zero regressions.
**Next action for next session:** re-run the fusion-vs-fission query
one more time to confirm B-014 actually surfaces relevant arXiv papers.
Also worth doing: commit this fix using the split convention (not
another squash), and consider whether to fix the comma-separated
citation regex gap noted in the previous entry.

### Entry 020
**Phase:** B-011/B-012 confirmed; B-013 found and fixed
**Action taken:** re-ran the fusion-vs-fission query. B-011 and B-012
both fully confirmed working on real hardware (exact previously-broken
case now works; zero arxiv failures across the whole run). Found B-013
in the same run — arXiv results still irrelevant despite successful
calls, same root cause as B-010 unapplied to a second tool. Fixed
identically. Also noted (not fixed) a citation-regex gap with
comma-separated multi-ID brackets.
**Decisions logged this run:** D-036.
**Debug entries logged this run:** B-012 closed, B-013 new, citation
regex gap noted as deliberately deferred.
**Regression status:** 113/113, zero regressions.
**Next action for next session:** re-run the fusion-vs-fission query
once more to confirm B-013's arXiv fix actually surfaces relevant
papers this time, not just well-formed queries. If retrieval quality is
still poor after this, the next suspects are web_search/news_search
result relevance or the curator's filtering — not yet investigated with
direct evidence either way.

### Entry 019
**Phase:** real evidence confirmed, 2 new bugs found and fixed
**Action taken:** clean re-extraction confirmed the stale-file theory
was correct. Re-ran both diagnostic queries with `--debug` on genuinely
fresh code. Confirmed three real successes (GitHub fix, citation_verifier,
B-007's primary path) and found two new real bugs in the same run:
B-011 (fallback logic gap — rejected-but-present search_query never
tried the fallback) and B-012 (arXiv rate limiting/timeouts, no
throttling existed). Fixed both.
**Decisions logged this run:** D-035 — full evidence writeup, all
confirmations and both new bugs.
**Debug entries logged this run:** B-010 marked closed; B-011 and B-012
new entries with root cause + fix + verification for each.
**Regression status:** 108/108, zero regressions.
**Next action for next session:** (1) commit everything per the split
convention already given (this session's B-011/B-012 fixes need their
own commit on top of the earlier D-027-D-034 batch), (2) re-run the
fusion-vs-fission query once more to confirm B-011's fix produces a
real refined query on the SECOND sufficiency check too (only the first
was confirmed working before this fix), (3) confirm B-012's arXiv
throttle actually eliminates the 429s/timeouts on a real run — sandbox
can't verify real network rate-limiting behavior.

### Entry 018
**Phase:** real evidence obtained, 3 fixes applied
**Action taken:** got real `--debug` output for both open questions.
Found and fixed two genuine bugs (Reddit's 403-on-every-call, GitHub's
natural-language-query mismatch) and traced a third symptom
(`refined_search_query=None`) to almost certainly be a stale local file
rather than a logic defect — verified the actual code is correct in
this sandbox, handed the user a direct check rather than asserting.
**Decisions logged this run:** D-034 — all three findings and fixes.
**Debug entries logged this run:** B-009 (Reddit), B-010 (GitHub).
**Regression status:** 105/105, zero regressions.
**Next action for next session:** (1) user to check whether their local
`src/rag/sufficiency.py` has the D-026 fallback code — if stale, a full
clean re-extraction (not a merge over the old folder) should resolve
B-007 without any further code changes. (2) re-run both `--debug`
queries after a clean sync to see if GitHub now returns results and
whether B-007 actually resolves once the stale-file question is settled.

### Entry 017
**Phase:** debuggability fix, blocking on real evidence
**Action taken:** ran the two requested real-hardware confirmations.
GitHub/Reddit didn't appear in a query expected to surface them; the
fusion-vs-fission query still failed to find fission sources (same
symptom as B-006). Investigated why I couldn't diagnose either
properly: found D-030 had an unflagged side effect — simplifying
`--verbose` also removed the sub_queries-list printing that made
B-005/B-006/B-007 diagnosable in the first place. Added `--debug`
(separate from `--verbose`) to restore that visibility plus per-tool
failure detail in `retriever_hybrid.retrieve()`, without reverting
D-030's clean default UX.
**Decisions logged this run:** D-033 — both findings, the D-030 side
effect, and the `--debug` design (spinner-bypass, same visual-conflict
reasoning as D-030).
**Debug entries logged this run:** none yet — the actual root causes of
the two real-run failures are still unknown, not yet debug-log-worthy
until `--debug` gives us evidence.
**Regression status:** 105/105, zero regressions.
**Next action for next session:** re-run BOTH queries with `--debug`
and report the full output. This is the actual next step for B-007 and
the GitHub/Reddit question — not a new item, the same two open items
from Entry 016, now with the tool needed to actually see what's
happening.

### Entry 016
**Phase:** New tools (GitHub, Reddit) + Phase 6 start
**Action taken:** in response to a combined request (confirm status +
start Phase 6 + add sources), gave an honest status check first rather
than a blanket "confirmed" — pointed out Phase 5's B-007 fix still lacks
real-hardware confirmation, and that "Phase 6" and "new sources" are
different scopes per our own docs. Then did both: added
`github_search`/`reddit_search` tools (no API key), explicitly declined
X/Twitter with reasoning (paid API requirement conflicts with `trd.md`).
Started Phase 6 with `verification/citation_verifier.py` — batched
per-answer entailment checking, wired into the agentic path only (per
already-logged D-006), fails open on parse failure.
**Decisions logged this run:** D-031 (new sources), D-032 (Phase 6
start, batched-not-per-claim design, explicit scope note that Phase 6
isn't complete).
**Debug entries logged this run:** none — clean implementation, all
failures caught were stale test fixtures (needed one more scripted
reply per test for the new verification call), not real bugs.
**Phase 6 exit criteria met?** No — explicitly not. One of three planned
modules built (`citation_verifier.py`). `answerability.py` and
`self_consistency.py` remain unbuilt.
**Regression status:** 105/105 across all 8 test files.
**Next action for next session:** real-hardware confirmation is now
owed on THREE fronts: (1) B-007's Phase 5 fix (oldest outstanding item),
(2) the new citation_verifier node in an actual agentic run, (3) the
new GitHub/Reddit tools against live endpoints. Recommend picking one
deliberately rather than letting the list keep growing unconfirmed.

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

### Entry 031
**Phase:** 6, closing the metric-mechanism gap (D-048)
**Action taken:** built `tests/eval/citation_accuracy_eval.py` (a
Phase-6-scoped eval harness, distinct from Phase 10's future
`golden_set.jsonl` — see `tests/eval/README.md`), a 12-query fixture
set, and `docs/eval_log.md` as the running, append-only log the harness
writes to. Validated the harness's aggregation/reporting logic with a
stub model in `test_phase6_citation_eval_harness.py` (18/18).
**Decisions logged this run:** D-048.
**Regression status:** 198/198 across the full 13-file suite.
**What this closes:** the mechanism half of Phase 6's remaining exit
criterion ("metric established and tracked"). The data half — an
actual real-hardware run producing a real accuracy number — is still
open, and folds into the same real-hardware batch already on hold per
Entry 030 (real hardware still needed for: Phase 6 answerability/self-
consistency confirmation, macOS/Linux Phase 8 builds, and now this
eval run too — `python tests/eval/citation_accuracy_eval.py`).
**Next action for next session:** unchanged in kind from Entry 030 —
still waiting on the user's real-hardware command output before any of
these can be marked done. Added the eval harness run to that same
waiting list rather than treating it as a new, separate ask.

### Entry 030
**Phase:** 6/8, on hold
**Action taken:** none — handed off testing commands for Phase 6
real-hardware confirmation and macOS/Linux Phase 8 builds (see D-047's
command list). User requested a pause: they'll discuss next steps first
and report command output afterward before this proceeds.
**Next action for next session:** wait for the user to provide real
command output. Do not run further code changes against Phase 6/8
assuming success — confirm from their actual output first.
