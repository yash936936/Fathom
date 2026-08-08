# TRD — Technical Requirements Document

> Redirect: after reading, return to `/context.md` for routing.

## 1. Hard constraints
- **Compute:** CPU-only for both development and runtime. No GPU assumed.
- **Memory:** <6GB RAM total budget for the running application, including
  model weights, KV cache, OS overhead, and app process.
- **Distribution:** single downloadable installer per OS; no requirement for
  user to have Python installed.
- **Connectivity:** live retrieval requires internet; core app must not crash
  if offline — must degrade to a clear "no live retrieval available" state.

## 2. Model
- **Base model:** Qwen3-4B-Instruct-2507
- **Format:** GGUF, Q4_K_M quantization (~2.4–2.6GB)
- **License:** Apache 2.0
- **Why:** native agentic tool-calling (Qwen-Agent), 262K native context,
  GQA (32 query / 8 KV heads) for cheap KV cache, meets RAM budget with
  headroom for cache + app overhead. Full rationale in `decisions.md` D-002.
- **Fine-tuning:** none in v1 (see `decisions.md` D-001). Revisit only if
  citation-accuracy evals show a specific, reproducible failure pattern that
  prompting/verification can't fix (see `phases.md` Phase 6 gate).

## 3. Inference stack
- **Engine:** llama.cpp via `llama-cpp-python` bindings.
- **Packaging:** PyInstaller (per-OS build, not cross-compiled — see
  `decisions.md` D-005).
- **Model delivery:** not bundled in the installer binary; downloaded on
  first install/run to a user-level cache directory, checksum-verified,
  resumable.

## 4. Retrieval stack
- **Strategy:** Adaptive RAG — complexity classifier routes queries to a fast
  single-pass path or the full agentic multi-hop path (see `code_logic.md`
  §Router).
- **Hybrid search:** BM25 + dense embeddings, fused via Reciprocal Rank
  Fusion, cross-encoder reranker on top.
- **Orchestration:** LangGraph state machine for the agentic path (planner →
  parallel retrieval → sufficiency check loop → synthesis → verification).
- **Tools:** web search API, news/trend feed, arXiv-style API, local vector
  DB of curated sources — behind a common tool-calling schema.

## 5. Guardrails & safety
- **Domain gate:** dedicated fast classifier (not prompt-only) — see
  `architecture.md` §Guardrail Layer.
- **Framework:** NeMo Guardrails (Apache 2.0) for input/dialog/output rails,
  paired with a lightweight classifier for topic-scoping.
- **Output verification:** per-claim citation entailment check before any
  answer is returned (see `code_logic.md` §Citation Verifier).
- **No system-prompt-only enforcement** — this is a control-flow requirement,
  not a request to the model.

## 6. Non-functional requirements
- **Latency:** REVISED per decisions.md D-022, based on real Phase 4
  measurement (375.7s for one fast-path query on reference CPU hardware —
  not an anomaly, see D-022's correction of the earlier D-015/D-016
  hypothesis). Original targets (<5s fast path / <20s agentic) are
  superseded, not achievable on the stated CPU-only/<6GB hardware profile
  with the current model. Fathom is scoped as a research tool where a
  multi-minute wait for a thorough, cited answer is acceptable — not an
  interactive chat tool. No hard latency ceiling is enforced in v1;
  `main.py`'s streaming output (D-021) exists specifically so a slow
  answer is visibly progressing rather than indistinguishable from a
  hang. Revisit only if a future eval shows latency is actually driving
  users away, with real usage data, not a pre-set number.
- **Reliability:** no silent hallucination fallback — retrieval failure must
  produce an explicit refusal, never a parametric-memory guess presented as
  grounded.
- **Portability:** Windows 10+, macOS 12+, major Linux distros (glibc-based),
  x86_64. ARM/Apple Silicon native builds tracked as stretch goal.
- **Update path:** model swap must not require reinstalling the app (model
  lives outside the install directory).

## 7. Evaluation
- Offline golden set (50–100 research queries) run before every release.
- Metric taxonomy (adapted from google/agents-cli's ADK eval framework —
  see `decisions.md` D-010): final response quality, instruction-following,
  tool-use quality, safety, hallucination — each scored per query, not
  averaged into one number.
- Tracked metrics: per-claim citation accuracy (not answer-level average),
  groundedness score, refusal correctness on off-domain set, retrieval
  sufficiency-loop retry rate, latency percentiles.
- Tooling: Ragas/Langfuse-style scoring, self-consistency sampling on the
  agentic path only (cost-gated — see `decisions.md` D-006).

## 8. Explicitly excluded from v1 architecture
- LLM gateway / multi-tenant serving layer (CLI runs in-process).
- Smart routing across multiple hosted models / fallback to hosted API.
- Multi-agent orchestration.
- Long-term cross-session memory store.
These remain documented in `architecture.md` as v2 extension points but are
not built until `phases.md` gates are met.

---
**Return to `/context.md` for next steps.**
