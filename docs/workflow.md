# workflow.md — Agent/Developer Working Process

> Redirect: after reading, return to `/context.md` for routing.
> This describes HOW to work (process discipline). `context.md` describes
> WHERE things are. Read both.

## 1. Session start checklist
1. Read `context.md`.
2. Read `docs/status.md` — confirm current phase and last logged action.
3. Read `docs/phases.md` — confirm current phase's file list and exit criteria.
4. Only open the specific docs/files that phase requires — don't read
   everything every session.

## 2. During work
- **Decisions:** the moment a design or code decision is made (model choice,
  library choice, algorithm choice, structural change), append it to
  `docs/decisions.md` immediately — not at session end, not batched.
- **Debugging:** the moment a bug is found AND resolved, append the full
  entry (symptom → root cause → fix → verification) to `docs/debug.md`
  immediately. Do not log a bug before it's resolved (that belongs in
  `status.md` as "in progress" instead).
- **Scope discipline:** if work drifts outside the current phase's file list
  (per `phases.md`), stop and either (a) confirm it's a legitimate
  cross-phase dependency and log why in `decisions.md`, or (b) defer it and
  note it in `status.md` as a follow-up.

## 3. Task completion checklist (every single task, no exceptions)
1. Update `docs/status.md`: what was done, what phase it belongs to, what's
   next.
2. Confirm any decisions made during the task are in `docs/decisions.md`.
3. Confirm any debugging done during the task is in `docs/debug.md`.
4. If a phase's exit criteria (per `phases.md`) are now met, note that
   explicitly in `status.md` so the next session knows to advance.
5. If a phase completes fully, update `docs/readme.md` to reflect new
   capabilities.
6. Return to `context.md` routing table for what's next.

## 4. Phase transition rule
Do not begin work listed under Phase N+1 in `phases.md` until Phase N's exit
criteria are explicitly confirmed met and logged in `status.md`. If blocked,
log the blocker in `status.md` rather than skipping ahead silently.

## 5. Conflict/ambiguity resolution
If two docs appear to disagree (e.g. `architecture.md` lists a file that
`phases.md` doesn't reference, or a constraint in `trd.md` seems violated by
a plan in `phases.md`):
1. Do not silently pick one — log the conflict in `status.md`.
2. Resolve in favor of `trd.md` constraints and `decisions.md` rationale
   (these represent settled reasoning) over `phases.md`/`architecture.md`
   convenience (these are working plans and may need updating).
3. Update the stale doc and note the correction in `decisions.md`.

## 6. What NOT to do
- Do not fine-tune the model without meeting the explicit revisit condition
  in `decisions.md` D-001.
- Do not add a gateway/service layer — see D-007.
- Do not batch decision/debug logging to "clean up at the end" — logs lose
  accuracy and context when written after the fact.
- Do not jump directly into a `docs/*.md` file without having read
  `context.md` first in the current session.

## 7. Git commit convention
One commit per logically-independent change, not one commit per session
or per phase. If a session produces work spanning multiple `decisions.md`
entries with genuinely separate reasoning (e.g. a UX feature plus an
unrelated bug fix found while testing it), that's multiple commits, not
one. A commit message should let someone reconstruct *why* from git log
alone, without needing to cross-reference `decisions.md` first — the ID
is a pointer for full detail, not a substitute for a real description.

Format:
```
<short imperative summary> (D-XXX[, B-XXX])

<1-3 sentences: what changed and why, in plain terms — not just a
restatement of the D-XXX title>
```

Examples matching this project's actual history:
```
Add quick/deep modes, spinner UI, verbose flag (D-027)

Quick mode skips the domain-gate LLM call and caps output length to
minimize latency as much as structurally possible on CPU-only hardware
-- not a guaranteed time ceiling, see D-027 for why one isn't promised.
```
```
Fix Reddit 403s and GitHub zero-results; extract shared text_utils (D-034, B-009, B-010)

Reddit blocks unauthenticated requests outright (100% failure, not
flaky) -- removed from the default tool list, module kept for future
opt-in use. GitHub's search API doesn't match natural-language question
sentences -- added query simplification via a new shared keyword
extractor, also used by rag/sufficiency.py's existing fallback logic.
```

Group by "what shipped together and was reasoned about together," not
by file touched or by calendar session. A single session's work often
becomes several commits; a single commit should never span unrelated
D-XXX entries just because they landed in the same conversation.

Commit `docs/` changes alongside the code they document, not separately
— a decisions.md entry describing a fix and the fix itself belong in
one commit, so `git log` and `git show` stay self-contained.

---
**Return to `/context.md` for next steps.**
