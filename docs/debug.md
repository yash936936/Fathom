# debug.md — Debug Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Append-only.** Every debug session, however small, gets an entry the
> moment it's resolved — do not batch these at end of session.
> Format: `B-XXX | phase | symptom | root cause | fix | files touched`

---

### B-000 — Template entry (do not delete; copy this shape for real entries)
**Phase:** —
**Symptom:** what broke / what was observed
**Root cause:** the actual underlying reason, not just the symptom
**Fix:** what was changed
**Files touched:** list of files
**Verification:** how it was confirmed fixed (test run, manual repro, eval)

---

### B-001 — llama-cpp-python cannot be verified end-to-end in this sandbox
**Phase:** 1
**Symptom:** `pip install llama-cpp-python` exceeded the sandbox execution
time limit; a follow-up background (`nohup ... &`) attempt also failed
silently -- the process was gone on the next check with an empty log.
**Root cause:** Two separate issues, not one: (1) llama-cpp-python has no
prebuilt wheel for this sandbox's platform/Python combination, so pip
falls back to compiling llama.cpp from source, which is slow; (2) this
sandbox does not persist background processes across separate tool
invocations, so `nohup ... &` is not a viable workaround here.
**Fix:** Not a code fix -- this is a sandbox limitation, not a bug in
Fathom. Verified everything that *is* verifiable without the compiled
dependency instead: `py_compile` on all three Phase 1 files (clean),
and the full CLI path with `llama_cpp` absent and the model file missing
-- confirmed the lazy-import design in `llm_backend.py` means
`ModelNotFoundError` raises correctly *before* ever touching the missing
`llama_cpp` import, so the error path degrades gracefully.
**Files touched:** none (verification only, no code change needed).
**Verification:** `python3 main.py "test"` → clean exit code 2 with the
correct actionable error message; `python3 main.py` (no args) → exit
code 1 with usage message; `--help` → correct argparse output.
**Follow-up for next session:** actual model-loading + generation
end-to-end must be verified on a real dev machine (or a sandbox with
network access to huggingface.co and enough time for the source build),
not in this container. Flag in `status.md` as an open verification gap,
not a closed exit criterion.

---
**Return to `/context.md` for next steps.**
