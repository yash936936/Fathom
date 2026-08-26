# phases.md — Phased Build Plan

> Redirect: after reading, return to `/context.md` for routing.
> Work phases in order. Do not start phase N+1 until phase N's exit criteria
> are met and logged in `status.md`. Every file listed maps to `architecture.md`.

## Phase 0 — Foundation & docs
**Files:** `context.md`, all `/docs/*.md` (this set)
**Goal:** doc scaffold complete and internally consistent.
**Exit criteria:** all docs cross-reference correctly; `status.md` initialized.

## Phase 1 — Core model backend (no RAG yet)
**Files:**
- `src/core/llm_backend.py`
- `src/core/state.py`
- `src/main.py` (minimal: load model, echo a completion)
**Goal:** Qwen3-4B-Instruct-2507 GGUF loads and generates via llama-cpp-python
within the <6GB budget on CPU.
**Exit criteria:** single hardcoded prompt → completion works end-to-end from
CLI invocation; memory footprint measured and logged in `status.md`.

## Phase 2 — Guardrail & domain gate
**Files:**
- `src/core/domain_gate.py`
- `src/core/guardrail.py`
**Goal:** off-domain queries are refused before any retrieval/generation
spend; input rails catch obvious prompt injection.
**Exit criteria:** eval set of in-domain vs off-domain queries hits ≥95%
correct routing (per `prd.md` success criteria).

## Phase 3 — Tools & hybrid retrieval
**Files:**
- `src/tools/registry.py`, `web_search.py`, `news_feed.py`, `arxiv_feed.py`, `vector_store.py`
- `src/rag/retriever_hybrid.py`
- `src/rag/reranker.py`
**Goal:** given a query, return ranked, fused (BM25+dense+RRF) results with
sources and dates attached.
**Exit criteria:** retrieval quality spot-checked against golden set queries;
tool registry supports adding a new tool without touching core logic.

## Phase 4 — Adaptive routing + fast path
**Files:**
- `src/core/router.py`
- `src/rag/synthesis.py` (fast-path mode: single retrieval pass → answer)
**Goal:** simple queries resolve end-to-end without the full agentic loop.
**Exit criteria:** fast-path latency target met (`trd.md` §6); citations
present on every fast-path answer.

## Phase 5 — Agentic path (LangGraph)
**Files:**
- `src/rag/planner.py`
- `src/rag/sufficiency.py`
- `src/rag/graph.py`
**Goal:** multi-hop queries are decomposed, retried with bounded loop,
synthesized.
**Exit criteria:** agentic path handles multi-hop golden-set queries;
retry loop respects cap (no runaway cost); latency target met.

## Phase 6 — Hallucination/verification layer
**Files:**
- `src/verification/answerability.py`
- `src/verification/citation_verifier.py`
- `src/verification/self_consistency.py` (agentic path only)
**Goal:** per-claim citation verification blocks ungrounded claims from
reaching the user; false-premise queries are caught pre-retrieval.
**Exit criteria:** per-claim citation accuracy metric established and
tracked (`trd.md` §7); this is the gate that decides whether fine-tuning
gets reconsidered (per `decisions.md` D-001) — only if this phase's evals
show a specific, reproducible gap that verification/prompting can't close.

## Phase 7 — Short-term memory
**Files:** `src/memory/conversation_buffer.py`
**Goal:** multi-turn conversation within a session retains context.
**Exit criteria:** follow-up queries correctly resolve references to prior
turns within the same CLI session.

## Phase 8 — Packaging (PyInstaller)
**Files:**
- `build/build_windows.py`, `build/build_macos.py`, `build/build_linux.py`
- `build/hooks/hook-llama_cpp.py`
**Goal:** per-OS standalone binary builds successfully, launches, runs a
query end-to-end.
**Exit criteria:** binary tested on all three target OSes; size/startup
optimized per `trd.md` NFRs.

## Phase 9 — Installer + seamless model download
**Files:**
- `build/windows/installer.iss`
- `build/macos/postinstall.sh`
- `build/linux/install.sh`
- `src/installer_support/model_downloader.py`
- `src/installer_support/first_run_check.py`
**Goal:** download-and-run experience — installer places binary, downloads
GGUF with progress + checksum, verifies model loads before declaring success.
**Exit criteria:** clean install → working `fathom` command on a
machine with nothing pre-installed, on all three OSes.
**Status (D-055/D-056, real-hardware confirmed D-057/D-058):**
**Windows track FULLY CLOSED** — `installer.iss` compiles with real
`ISCC.exe`, `fathom-setup.exe` runs and installs correctly, both Start
Menu shortcuts confirmed present, the model downloads with a checksum
confirmed correct against the real file, and the installed binary
produces real grounded answers. Linux `install.sh` functionally
tested end-to-end on a real Linux machine (this project's sandbox),
though not yet via a packaged/distributable installer flow the way
Windows now has. **Still not done:** macOS `postinstall.sh` — needs a
real Mac, none available. Exit criteria met in full on Windows; Linux
close but not identical in form; macOS genuinely blocked pending
hardware access.

## Phase 10 — Evaluation, hardening, release prep
**Files:** `tests/eval/golden_set.jsonl`, `tests/unit/*`
**Goal:** full eval suite passing against `prd.md` success criteria.
**Judge model:** a separate offline open-source model (Llama-3.1-8B-
Instruct GGUF), not Qwen3-4B judging itself and not a hosted API — see
`decisions.md` D-049.
**Exit criteria:** metrics logged in `status.md`; `readme.md` finalized;
tag v1.0.
**Status (D-059):** `golden_set.jsonl` built (32 entries — a starting
set, not yet the full 50-100) and `golden_set_eval.py`, scoped to the
two `prd.md` §5 criteria nothing previously measured (off-domain
refusal rate, zero-silent-hallucination via an honest proxy check).
Citation accuracy already covered by Phase 6's tooling, not
duplicated. **Not yet done:** no real run; `tests/unit/*` (the
existing 19-file test suite is still scattered at repo root, not
reorganized into this structure — deferred as a separate, careful pass
given the real risk of breaking `sys.path` assumptions across every
existing test file); `readme.md` finalization; v1.0 tag.

## v2 (not started until v1 ships and is stable)
Long-term memory, smart routing/fallback across hosted models, multi-agent
orchestration, LLM gateway for multi-user mode. Extension points already
documented in `architecture.md` §5 — do not build early.

---
**Return to `/context.md` for next steps.**
