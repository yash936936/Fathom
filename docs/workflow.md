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

---
**Return to `/context.md` for next steps.**
