# decisions.md — Decision Log

> Redirect: after reading/writing, return to `/context.md` for routing.
> **Append-only.** Never edit or delete a past entry — if a decision is
> reversed, add a new entry that supersedes it and link back (e.g. "Supersedes D-002").
> Format: `D-XXX | date/phase | decision | rationale | alternatives rejected`

---

### D-001 — No fine-tuning in v1
**Phase:** 0 (planning)
**Decision:** Drop LoRA/QLoRA fine-tuning from the v1 architecture entirely.
**Rationale:** Core requirement is freshness (daily-updating trends), which
fine-tuning cannot provide — weights are frozen at training time. Selected
base model (Qwen3-4B-Instruct-2507) already has strong native tool-calling
via Qwen-Agent, removing the other reason fine-tuning was originally
considered. Domain-scoping is a control-flow problem (classifier gate), not
a model-behavior problem, so fine-tuning doesn't help there either.
**Revisit condition:** only if Phase 6 citation-accuracy evals show a
specific, reproducible gap that verification/prompting cannot close — and
then only a narrow LoRA pass on citation formatting, never knowledge
injection.
**Alternatives rejected:** full fine-tune (cost/time prohibitive on stated
constraints); QLoRA on CPU (impractical — see D-004).

### D-002 — Base model: Qwen3-4B-Instruct-2507
**Phase:** 0 (planning)
**Decision:** Use Qwen3-4B-Instruct-2507, GGUF Q4_K_M quantization, as the
sole inference model.
**Rationale:** Apache 2.0 license; native agentic tool-calling (Qwen-Agent);
GQA (32 query/8 KV heads) keeps KV cache cheap; 262K native context; ~2.4–2.6GB
at Q4_K_M fits comfortably under the <6GB total budget with headroom for
cache/OS/app.
**Alternatives rejected:** Llama 3.1-8B (larger footprint, weaker multi-turn
coherence per comparative LoRA benchmarks); Phi-4-mini (strong reasoning but
limited factual/world knowledge, less proven agentic tool-calling ecosystem);
Qwen2.5-3B (superseded by Qwen3 generation's better tool-calling).

### D-003 — Multi-agent orchestration deferred to v2
**Phase:** 0 (planning)
**Decision:** Single-agent LangGraph RAG loop only in v1. No multi-agent
orchestration (separate search/synthesis/critic agents).
**Rationale:** Added orchestration complexity only justified once single-agent
RAG demonstrably plateaus on real eval data — building it speculatively risks
infrastructure-before-value.
**Revisit condition:** Phase 10 eval results show single-agent ceiling hit on
a specific, identifiable failure class.

### D-004 — Fine-tuning/training compute, if ever needed, is not CPU-local
**Phase:** 0 (planning)
**Decision:** If any future fine-tuning is undertaken (per D-001 revisit
condition), it will use rented/cloud GPU compute for the training step only —
never CPU-only training.
**Rationale:** QLoRA depends on bitsandbytes' CUDA-based 4-bit training path;
no mature CPU-only equivalent exists at comparable speed. A full LoRA run
costs approximately $4 and under an hour on rented GPU vs. days-to-weeks on
CPU for identical output.
**Note:** this does not violate the CPU-only *runtime/dev* constraint — that
constraint governs the shipped application and day-to-day dev loop, not a
one-time, isolated training job.

### D-005 — Packaging: PyInstaller, per-OS builds via CI matrix
**Phase:** 0 (planning)
**Decision:** Use PyInstaller for each target OS, built via a CI matrix
(GitHub Actions: windows-latest/macos-latest/ubuntu-latest), not a single
cross-compiled artifact.
**Rationale:** PyInstaller is not a cross-compiler by design — it bundles a
native Python interpreter and must run on the OS it targets.
**Alternatives rejected:** Nuitka/cx_Freeze (less mature ecosystem support
for llama-cpp-python's compiled binary dependency).

### D-006 — Verification cost is gated by adaptive routing
**Phase:** 0 (planning)
**Decision:** Heavy hallucination-verification steps (self-consistency
sampling, per-claim entailment) apply only on the agentic path. Fast path
gets structural checks only (citation tag present + citation ID resolves).
**Rationale:** Mirrors the adaptive-RAG cost/quality tradeoff already applied
at the routing layer — spend verification budget where risk (multi-hop,
ambiguous) is highest, not uniformly across all queries.

### D-007 — No gateway/microservice layer for the CLI
**Phase:** 0 (planning)
**Decision:** All components (guardrail, router, RAG, verification) run
in-process within the single CLI application. No LiteLLM-style gateway,
no service boundaries, no auth/rate-limiting layer in v1.
**Rationale:** Gateway patterns solve multi-tenant/service problems the CLI
doesn't have — a single-user local tool calling itself in-process doesn't
need network-hop infrastructure. Documented as a v2 extension point only if
a hosted/multi-user mode is ever built.

### D-008 — Model not bundled in installer; downloaded on install
**Phase:** 0 (planning)
**Decision:** The installer/binary ships without the GGUF weights; the model
(~2.5GB) downloads during install (or first run as fallback), to a user-level
cache directory, with progress indication, checksum verification, and resume
support.
**Rationale:** Keeps the distributable small (~50–150MB), avoids re-shipping
the whole binary on every model update, avoids slow PyInstaller `--onefile`
unpack of a multi-GB payload on every launch.
**Alternatives rejected:** full bundling (simpler offline-from-download-one
UX, but with real cost in binary size, build time, and update friction) —
left as a documented optional variant, not the default.

### D-009 — Domain enforcement is a classifier gate, not a system prompt
**Phase:** 0 (planning)
**Decision:** Research-only scope is enforced via a dedicated fast classifier
node before any retrieval/generation spend, backed by NeMo Guardrails input/
output rails — never relies on system-prompt instruction alone.
**Rationale:** System-prompt-only scoping is easily overridden and fails
silently; a control-flow gate is auditable, logs violations, and is cheaper
(rejects before burning retrieval budget).

### D-010 — External repo review: 3 patterns adopted, rest rejected/deferred
**Phase:** 0 (planning)
**Decision:** Reviewed 12 externally suggested GitHub repos for reusable
logic. Adopted (as logic patterns, not dependencies — no code copied):
1. **Curator node** (guy-hartstein/company-research-agent) — added
   `rag/curator.py`, a relevance/quality/recency filter pass between
   reranking and the sufficiency check. See `code_logic.md` §4, §9.
2. **Retry-cap-with-explicit-caveat** (cobusgreyling/loop-engineering) —
   sharpened the sufficiency-loop behavior so cap exhaustion surfaces as a
   visible caveat in the final answer, never a silent fallback. Their
   failure-mode catalog explicitly names "loop stuck retrying, human never
   notified" as a known anti-pattern — our design avoids it by construction.
   See `code_logic.md` §4.
3. **Eval metric taxonomy** (google/agents-cli) — adopted their category
   split (response quality / instruction-following / tool-use quality /
   safety / hallucination) for our own eval framework. See `trd.md` §7.

**Deferred to v2 (documented as extension points, not built):**
- `tools/browser_tool.py` — pattern from browser-use/browser-harness (CDP
  browser automation). Too heavy for v1 (Chrome runtime dependency).
- `tools/social_trends.py` — pattern from Panniantong/Agent-Reach (free,
  cookie-based Reddit/Twitter/YouTube access). Useful for the trend-tracking
  requirement but expands dependency surface; kept optional/pluggable.
- Managed tool-integration backend — pattern from ComposioHQ/composio
  (schema-driven multi-toolkit access). Confirms our existing
  `tools/registry.py` design direction but not adopted as a v1 dependency:
  requires a cloud API key/account, conflicting with `trd.md`'s
  "no API key required for core operation" requirement.
- Long-term memory reference concepts (contradiction detection, citation
  auto-fixing) from garrytan/gbrain — noted for `memory/long_term_store.py`
  if/when v2 memory is built. Rejected wholesale adoption: reference
  deployment needs Postgres + embedder service + 8GB+ RAM, directly
  conflicting with `trd.md` §1's <6GB CPU-only constraint.

**Rejected outright (no fit):**

- agentskills/agentskills — coding-agent skill packaging spec, wrong
  problem domain for an end-user research CLI.
- repowise-dev/repowise — codebase intelligence for coding agents, not
  applicable.
- daveshap/OpenAI_Agent_Swarm — hosted-API-only hierarchical swarm,
  archived project; overlaps with multi-agent orchestration already
  deferred per D-003.
- kju4q/q-agent-harness — could not verify this resolves to a real,
  identifiable repo matching the description given; no logic extracted.
- lyogavin/airllm — layer-by-layer disk-streaming technique for shrinking
  GPU VRAM needs. Conceptually interesting but VRAM/`accelerate`-specific
  with no confirmed CPU-RAM equivalent; not needed since Qwen3-4B already
  fits the RAM budget whole (see D-002). Noted only, not adopted.

### D-011 — Project name: Fathom
**Phase:** 0 (planning)
**Decision:** Project and CLI command name set to **Fathom** (`fathom
"query"`).
**Rationale:** Verified against PyPI/GitHub before shortlisting. Earlier
candidates rejected on collision/confusion grounds: "Scout" — multiple
active, well-known PyPI packages (`scout`, `scout-cli`, `ScoutSuite`,
`scout-apm`) in the same CLI-tool ecosystem; "Verity" — `verity-rag` is an
active package in the near-identical domain (RAG document retrieval),
plus `verity-sdk`/`verity-guard`/`VerityPy` crowding; "Ledger" — heavy
collision with both accounting software (`django-ledger`, `ledger-cli-
toolkit`) and the Ledger crypto hardware wallet ecosystem. "Fathom" has no
bare-name PyPI collision and no exact GitHub project match; nearest
neighbors (`fathomnet-py`, `fathom-python`, Fathom Analytics) are
adjacent-but-distinct enough not to cause practical confusion for a
research CLI. User made the final call between Fathom and the alternate
clean candidate "veriscout."
**Files updated:** `readme.md`, `context.md`, `architecture.md`,
`phases.md`, `appflow.md` — all `research-cli` placeholder references
renamed to `fathom`.
**Note:** domain/trademark availability (e.g. fathom.dev) was not checked —
only PyPI and GitHub were verified. Confirm separately before any public
launch or domain registration.

### D-012 — Phase 1 implementation choices: n_ctx, threading, lazy import, argparse
**Phase:** 1
**Decision:** Several concrete choices made while writing `core/state.py`,
`core/llm_backend.py`, `main.py`:
1. **Default `n_ctx=8192`**, not Qwen3's full 262,144-token native max.
   KV cache scales with context length and has to share the <6GB budget
   with the ~2.4–2.6GB of model weights (`trd.md` §1). 8192 is a
   starting point, not a final number — Phase 1's exit criteria call for
   measuring actual memory footprint and logging it in `status.md`;
   revisit this constant once that measurement exists.
2. **`n_threads=os.cpu_count()`, `n_gpu_layers=0` explicit.** The GPU
   layer count is hardcoded to 0 rather than left at llama-cpp-python's
   default, since `trd.md` §1's CPU-only constraint is a hard requirement,
   not a preference — an explicit 0 fails loudly if that ever changes
   silently upstream.
3. **`llama_cpp` imported lazily inside `FathomModel.__init__`, after the
   model-file-exists check**, not at module top level. This means
   `ModelNotFoundError` (a clear, actionable CLI error) fires before any
   dependency-import error would, and the module is importable even in
   environments where `llama-cpp-python` isn't installed yet (e.g. running
   `state.py`'s tests in isolation later).
4. **`argparse` over `click`/`typer` for Phase 1's CLI**, despite
   `architecture.md` listing "typer/click" as the intended entrypoint
   library. Rationale: Phase 1's scope is a single positional arg plus
   one flag — stdlib argparse covers it with zero added dependencies.
   Revisit when Phase 4+ needs subcommands or richer flag handling; not
   a hard commitment either way, just avoiding a premature dependency.
**Files touched:** `src/core/state.py`, `src/core/llm_backend.py`,
`src/main.py`, `requirements.txt`.
**Verification:** see `debug.md` B-001 — syntax and CLI-path verification
done; full model-load/generation verification deferred to a real dev
machine per that entry's follow-up note.

### D-013 — Phase 2 ships a lightweight custom guardrail, not NeMo Guardrails
**Phase:** 2
**Decision:** `core/guardrail.py` implements input/output rails as plain
regex heuristics and structural checks, with no external dependency —
NOT the NeMo Guardrails integration `trd.md` §5 names as the target
framework.
**Rationale:** This is an explicit, logged deviation from `trd.md`, not a
silent one (per `workflow.md` §5 conflict-resolution rule). NeMo
Guardrails is a real dependency with its own config/Colang layer; adding
it before there's eval data showing the lightweight version is
insufficient would be the same premature-dependency mistake flagged in
D-012 point 4. The control-flow principle D-009 actually requires (a
classifier gate that runs before spend, not prompt-only enforcement) is
fully satisfied by `core/domain_gate.py` regardless of which library
backs `guardrail.py`.
**Revisit condition:** if Phase 2's eval-set testing (once Phase 1 is
confirmed and a golden set exists) shows the regex-based injection
detection has a meaningful false-negative rate that NeMo Guardrails'
more sophisticated detection would close, swap the implementation behind
`input_rail()`/`output_rail()`'s existing function signatures — callers
in `main.py`/`router.py` shouldn't need to change.
**Files touched:** `src/core/guardrail.py`.
**Verification:** see `debug.md` B-002, B-003 — two real bugs found and
fixed via `test_phase2_manual.py`'s stubbed-model test harness (13/13
passing after fixes), plus a manual false-positive spot-check against
three realistic in-domain queries.

### D-014 — Started Phase 2 before Phase 1 exit criteria were confirmed
**Phase:** 2
**Decision:** Proceeded to Phase 2 on explicit user instruction ("Phase
2"), despite `workflow.md` §4's phase-transition rule stating Phase N+1
shouldn't start until Phase N's exit criteria are confirmed met — Phase
1 remains blocked on real-hardware verification (see `debug.md` B-001,
`status.md` Entry 004).
**Rationale:** This is a deliberate, informed override by the user, not
an agent decision to skip the rule. Logged per `workflow.md`'s own
guidance that scope/process deviations get logged, not silently applied.
Phase 2's code (`domain_gate.py`, `guardrail.py`) has no runtime
dependency on Phase 1's unresolved verification gap — it depends on
`FathomModel`'s interface (which is stable/tested), not on the model
actually being loadable in this sandbox — so the work itself isn't
blocked, only the "is Phase 1 truly done" confirmation is.
**Follow-up:** when Phase 1 is verified on real hardware, also run
Phase 2's `classify_domain()` against the real model (not the stubbed
one in `test_phase2_manual.py`) before treating Phase 2 as verified —
the stub only proves the parsing/control-flow logic, not that the real
Qwen3-4B model actually produces classifications matching the expected
JSON shape reliably.

### D-015 — Real-hardware verification: correctness confirmed, latency fails trd.md targets
**Phase:** 1/2 (verification)
**Finding:** User ran `verify_real_model.py` on real hardware (Windows,
Git Bash/MINGW64). Correctness results are good: model loads and
generates coherent output; `classify_domain()` hit 5/5 on a real-model
smoke test (confidence 0.95–0.99) including correctly catching an
injection-style query. This closes the D-014 follow-up condition — Phase
2's logic is no longer stub-only-verified.
**Problem:** Performance fails `trd.md`'s stated latency targets outright,
not marginally. Measured: model load 68.2s; generation ~2 tokens/second
(46.6s for a ~40-token reply). A single domain-gate call alone would
exceed the entire fast-path 5s budget before any retrieval or synthesis
even starts.
**Decision:** Do not proceed to Phase 3 (tools/retrieval) until this is
diagnosed — building a RAG pipeline on top of ~2 tok/s inference would
compound the problem, not reveal anything new about it. Most likely
cause: the `pip install llama-cpp-python` wheel installed without
CPU-specific SIMD acceleration (AVX2/AVX-512) for the user's hardware,
which is a common default on Windows pip installs. Not yet confirmed —
this is a hypothesis to test, not a diagnosis.
**Next action:** user to run a CPU capability check and reinstall
llama-cpp-python with explicit acceleration flags if AVX2 is available
but unused; report back before Phase 3 starts.
**Files touched:** none yet — diagnosis first, code changes (if any,
e.g. adjusting `n_threads`/`n_ctx` defaults in `llm_backend.py`) come
after root cause is confirmed, not before.

### D-016 — D-015's SIMD hypothesis was wrong; root cause still open
**Phase:** 1/2 (verification, continued)
**Finding:** User's verbose model-load output confirms full SIMD
acceleration is active: `AVX = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 |
AVX512 = 1 | REPACK = 1`, with weight repacking (`q4_K_8x8`) also
engaged, and `os.cpu_count()` correctly reports 8 threads. D-015's
hypothesis (missing SIMD in the pip wheel) is therefore ruled out —
logged here rather than silently dropped, since a wrong hypothesis is
still a useful data point for whoever debugs this next.
**Still unexplained:** ~0.9 tok/s generation is roughly 10-20x slower
than expected for a 4B Q4 model with this hardware profile. Root cause
not yet identified.
**Decision:** Still holding Phase 3 until this is isolated — proceeding
now would mean building and tuning the RAG/tool layer against an
unexplained, likely-artificial performance ceiling. Next diagnostic
steps handed to the user: (1) close VS Code / other CPU-competing
processes and re-test from a plain terminal, (2) confirm Windows power
plan is not throttling (Balanced/Power saver/on-battery), (3) if neither
resolves it, test whether Windows Defender real-time scanning is
interfering with the large mmap'd model file during inference.
**Files touched:** none — still diagnosis-only, no code changes made in
response to an unconfirmed root cause.

### D-017 — use_mmap=False: confirmed ~2x generation speedup, real memory tradeoff
**Phase:** 1/2 (verification, resolved partially)
**Finding:** User tested `use_mmap=False` directly: generation time for
the same ~40-token reply dropped from 42.3s to 23.6s (~1.7 tok/s, up from
~0.9 tok/s). This confirms disk I/O via memory-mapping was a real,
measurable contributor to the slowdown on the reference dev machine —
not the whole story (still well short of `trd.md`'s <5s fast-path
target), but a genuine, reproducible improvement, not noise.
**Decision:** Set `use_mmap=False` as the default in
`core/llm_backend.py`, not left as a manual flag.
**Tradeoff, stated plainly:** this is not a free win. `use_mmap=True`
(llama.cpp's default) lets the OS page model weights in/out of RAM on
demand; `use_mmap=False` forces the full ~2.3GB file into resident
process memory upfront. Against `trd.md` §1's <6GB budget, this is a
real cost, not a rounding error — it trades some memory headroom for
generation speed. Flagged here rather than presented as a strictly
better default.
**Still open:** ~1.7 tok/s remains below the `trd.md` latency target.
This is a partial fix, not a resolution — root cause of the *remaining*
gap (Defender scanning, thermal/power throttling, or something else) is
still undiagnosed. Not blocking Phase 3 any further per the override
below (D-018), but the gap is carried forward as a known, unresolved
risk, not silently dropped.
**Files touched:** `src/core/llm_backend.py`.

### D-018 — Proceeding to Phase 3 with latency gap still open (explicit override)
**Phase:** 3
**Decision:** User asked to proceed twice in a row despite the
unresolved latency gap (first "phase 4," corrected to Phase 3 given
`phases.md`'s dependency order). Per the same pattern as D-014, this is
logged as a deliberate, informed override — the user has now seen the
diagnostic trail (D-015 wrong hypothesis, D-016 disproven, D-017 partial
fix) and chosen to proceed rather than keep debugging further right now.
**Risk carried forward, not resolved:** Phase 3's retrieval/tool layer
will be built and tested against a model that still generates at
roughly 1.7 tok/s against a <5s fast-path target. Anything built in
Phase 3 that assumes fast per-call LLM turnaround (e.g. multiple
sub-query calls in the agentic path, Phase 5) will need re-evaluation
once the underlying latency issue is actually resolved.
**Follow-up:** the remaining latency gap stays open in `status.md`
blockers — not closed, just deprioritized relative to making forward
progress on functionality first.

### D-019 — Phase 3 ships BM25-only retrieval, no dense embeddings or cross-encoder reranker
**Phase:** 3
**Decision:** `rag/retriever_hybrid.py` and `rag/reranker.py` implement
lexical (BM25) retrieval and a heuristic (BM25-score + recency-boost)
reranker. Neither ships the dense-embedding half of "hybrid" search nor
a learned cross-encoder reranker that `trd.md` §4 originally named as
the v1 target.
**Rationale:** Both real options for dense embeddings/cross-encoder
reranking (sentence-transformers-class models) depend on `torch`, which
is a large, heavy dependency that directly conflicts with `trd.md` §1's
CPU-only/<6GB constraint — the same category of problem already flagged
for NeMo Guardrails in D-013 and the tool-integration platforms rejected
in D-010. This is an explicit, logged deviation from `trd.md`, not a
silent one (`workflow.md` §5).
**Alternative considered and rejected for now:** using the already-loaded
Qwen3-4B model itself in embedding mode (llama.cpp supports this) to
avoid adding a new dependency. Rejected because it would require a
second model instance loaded simultaneously (one for chat, one for
embeddings), roughly doubling the already-tight RAM budget — worse than
the dependency-weight problem it would solve.
**Revisit condition:** if Phase 6/10 eval data shows BM25-only retrieval
has a specific, reproducible recall gap that dense retrieval would close,
revisit with a concrete lightweight-embedding option in hand (e.g. a
small ONNX-runtime-based embedding model, which avoids torch) rather
than defaulting to sentence-transformers.
**Naming note:** `tools/vector_store.py` keeps its name from
`architecture.md` despite not being a vector store in v1 — the
`RetrievedChunk`-shaped interface is stable, so a real dense backend can
be swapped in later without touching callers in `rag/retriever_hybrid.py`.
**Files touched:** `src/tools/registry.py`, `src/tools/web_search.py`,
`src/tools/arxiv_feed.py`, `src/tools/news_feed.py`,
`src/tools/vector_store.py`, `src/rag/retriever_hybrid.py`,
`src/rag/reranker.py`, `requirements.txt`.
**Verification:** see `debug.md` B-004 for a real bug found and fixed
during this phase (tool self-registration via import side-effects).
11/11 checks passing in `test_phase3_manual.py` for everything testable
without network access (registry, BM25 store, dedupe, reranker logic).
`web_search.py`/`arxiv_feed.py`/`news_feed.py`'s actual network/parsing
against live endpoints is UNVERIFIED in this sandbox (same limitation as
B-001) — needs testing on a real machine before Phase 3 is marked
complete.

### D-020 — Phase 3 fully verified on real hardware; router is heuristic, not an LLM call
**Phase:** 3 completion + 4
**Phase 3 closure:** user ran `test_phase3_manual.py` (11/11) and
`verify_phase3_network.py` on real hardware with live network access.
All three network tools confirmed working against real endpoints
(DuckDuckGo HTML, arXiv Atom API, Google News RSS all returned correctly
parsed, dated results for a live query). `retriever_hybrid.retrieve()` +
`reranker.rerank()` end-to-end also confirmed: recency-weighted ranking
correctly favored same-week arXiv/news results over an older item and
over undated web results, in the exact stable order the scoring logic
predicts. Phase 3 is genuinely complete, not just code-complete.
**Phase 4 decision:** `core/router.py`'s complexity classification is a
pure heuristic (regex/word-count signals), not an LLM call. Given the
still-open latency problem (D-015/D-017/D-018), adding a third LLM call
per query (domain_gate, then a routing call, then synthesis) would make
routing itself a bottleneck for no accuracy benefit a cheap heuristic
can't already provide — comparison words, multi-part phrasing, question
count, and query length are reasonable, explainable proxies for "needs
decomposition."
**Latency now concrete, not abstract:** Phase 4 wires domain_gate +
retrieve + rerank + synthesis into one real end-to-end call chain. At
current measured speeds (~1.7 tok/s post D-017), a single fast-path query
now realistically costs 60-90+ seconds (domain-gate call + synthesis
call, each generating tens of tokens). This was flagged to the user
directly before writing Phase 4's code, not discovered silently after.
**Files touched:** `src/core/router.py`, `src/rag/synthesis.py`,
`src/main.py` (full rewrite from Phase 1's raw passthrough to the wired
fast-path pipeline), `test_phase4_manual.py`.
**Verification:** 17/17 logic checks passing in `test_phase4_manual.py`
(router heuristics, citation extraction including the "cited a
nonexistent source_id gets flagged immediately at parse time, no LLM
call needed" case, and the zero-retrieved-chunks explicit-refusal path
that never calls the model at all). Full end-to-end `main.py` run with
the real model is NOT yet verified — needs the user to run it, same
pattern as every prior phase.

### D-021 — Added token streaming after a real 15-minute silent run looked indistinguishable from a hang
**Phase:** 4
**Finding:** User's first real end-to-end `main.py` run produced zero
output for 15+ minutes before being interrupted. Root cause: `chat()`
was non-streaming (`create_chat_completion` without `stream=True`
blocks until the entire response is generated), and Phase 4's default
`max_tokens=512` combined with ~1.7 tok/s generation (post-D-017) means
a full-length answer could take 5+ minutes of raw generation alone, on
top of the domain-gate call and prefill time for a prompt now containing
several retrieved sources. The run may well have still been progressing
normally — there was simply no way to tell from the user's side.
**Decision:** Added optional token-by-token streaming to
`core/llm_backend.py`'s `chat()` (via an `on_token` callback,
`stream=True` under the hood) and threaded it through
`rag/synthesis.py`'s `generate()`. `main.py` now prints stage progress
("Checking request...", "Searching sources...", "Generating answer from
N sources...") and streams the answer live token-by-token as it's
generated.
**Scope of the fix:** this addresses the UX/legibility problem (is it
working or hung), NOT the underlying latency problem (D-015/D-017/D-018
remain open). A slow answer that visibly streams is still a slow answer.
Not conflating the two.
**Files touched:** `src/core/llm_backend.py`, `src/rag/synthesis.py`,
`src/main.py`.
**Verification:** `test_phase4_manual.py` re-run after the refactor —
still 17/17, confirming the non-streaming code paths (citation
extraction, zero-chunk refusal, router heuristics) are unaffected by
`on_token` defaulting to `None`. The actual streaming behavior itself
is NOT verified in this sandbox (needs the real model) — user to
re-run `main.py` with a small `--max-tokens` first for a fast
confirmatory pass, per this turn's guidance.

### D-022 — Phase 4 confirmed working end-to-end; latency target reframed, not abandoned
**Phase:** 4 completion + 5
**Phase 4 closure:** real end-to-end run on user's hardware succeeded
functionally: retrieval pulled real live sources, synthesis correctly
hedged rather than fabricating ("no specific mention of breakthroughs
beyond these points"), and both citations in the answer resolved to
real, listed sources — the core grounding behavior the citation/
guardrail design exists to produce is confirmed working, not just
theoretically sound. Measured latency: 375.7s for one fast-path query
(domain gate + retrieval + synthesis), ~75x over `trd.md`'s original <5s
target.
**Correction to earlier framing:** D-015/D-016 assumed the slowness was
an anomaly with a findable root cause, based on best-case benchmark
throughput for this model class. Having ruled out missing SIMD
(disproven, D-016), disk I/O via mmap (partially fixed, D-017), and
threading (confirmed correct), the remaining gap looks more like this
laptop's real sustained CPU-inference ceiling than a bug still waiting
to be found. Stated plainly rather than continuing to search for a fix
that may not exist.
**Decision:** User chose explicitly (asked directly, not another silent
override) to accept current latency and continue, framing Fathom as a
research tool where a multi-minute wait for a thorough, cited answer is
an acceptable tradeoff — not a chat tool needing sub-5-second turnaround.
**trd.md updated accordingly:** the <5s/<20s latency targets in `trd.md`
§6 are revised, not deleted — see the corresponding edit there. This is
a real scope decision, not scope creep silently absorbed.
**Carried forward into Phase 5, explicitly:** the agentic path adds a
planner call, up to 3 retry-loop iterations, and the same synthesis
call — each paying a similar per-call cost to what's now measured. A
complex query could realistically take considerably longer than 375s.
This is accepted, not hidden, per the user's explicit choice above.
**Files touched:** `docs/trd.md` §6 (NFRs updated), `docs/phases.md`
(Phase 4 exit criteria reinterpreted under the revised target).

### D-023 — Phase 5 built: LangGraph agentic path, curator implemented, no LLM calls added where heuristics suffice
**Phase:** 5
**Decision:** Added `langgraph>=1.0` as a real dependency — pure
control-flow library, no heavy compute backend, doesn't conflict with
`trd.md` §1 the way torch-based options did (D-013, D-019). Built
`rag/planner.py`, `rag/curator.py` (finally implementing the node
documented back in D-010 but never coded), `rag/sufficiency.py`, and
`rag/graph.py` wiring them into the exact node graph specified in
`code_logic.md` §4.
**Given D-022's accepted-but-real latency cost per LLM call:**
`rag/curator.py` is deliberately a heuristic filter (content length,
alpha-character ratio, query-word overlap), not an LLM call — every
avoidable model call matters more now that each one is confirmed
expensive (375s baseline from D-022). `MAX_RETRIES` set to 2 (low end of
`code_logic.md`'s "2-3" range) for the same reason — each retry is
another full retrieval + sufficiency-check round trip.
**UX consistency with D-021:** added stage-progress printing inside
`rag/graph.py`'s node closures (planner, each retrieval attempt,
sufficiency check, synthesis) — the agentic path chains more LLM calls
than the fast path, so silent waiting would be an even worse version of
the problem D-021 fixed. Full token-by-token streaming (like the fast
path's synthesis) is NOT wired into the agentic path's synthesis node
yet — stage markers only, not live token output. Noted as a gap, not
silently left unstated.
**Files touched:** `src/rag/planner.py`, `src/rag/curator.py`,
`src/rag/sufficiency.py`, `src/rag/graph.py`, `src/main.py` (complex
path now calls `run_agentic()` instead of the Phase 4 placeholder
message), `requirements.txt`.
**Verification:** this phase has the strongest verification of any so
far — 13/13 in `test_phase5_manual.py` (planner/curator/sufficiency unit
logic) AND 9/9 in `test_phase5_graph.py`, which runs the actual compiled
LangGraph state machine end-to-end with a scripted stub model across
three scenarios: immediate success (3 calls), one retry then success (4
calls, retry_count confirmed incremented exactly once), and retry-cap
exhaustion (confirmed `retry_count` stops exactly at `MAX_RETRIES` and
the evidence gap is surfaced in the final answer rather than dropped).
This is real orchestration-framework verification, not just isolated
function testing — but still stub-based; the real model + real network
combination for the full agentic path is NOT yet verified, same pattern
as every prior phase.

### D-024 — Phase 5 real-hardware run: correct end result, but exposed a genuine retry-loop bug
**Phase:** 5, real verification
**Finding:** first live agentic run (comparison query) completed in
444.1s and produced a correct, honest answer — it recognized the
sources had no fission-reactor data and said so explicitly rather than
fabricating a comparison, and the retry cap/gap-surfacing mechanics
worked exactly as designed. But inspecting *why* it never found
fission-related evidence revealed a real bug: see `debug.md` B-005 —
retries were silently re-running identical sub-queries and discarding
prior evidence each time, so the 3 "attempts" shown in the stage output
weren't actually searching for anything new. The end result was correct
by luck of honest refusal, not because the retry mechanism was doing
its job.
**Why this matters more than a typical bug:** at ~150s+ per retrieval/
sufficiency round trip (per D-022's accepted cost), a retry loop that
doesn't actually refine its search is close to pure wasted time —
exactly the kind of cost this project can least afford to spend
pointlessly, given the latency situation is already accepted as a
real, known constraint.
**Fixed:** see B-005 for the full fix (evidence accumulation across
retries + gap-based sub_query refinement, both previously documented in
`code_logic.md` §4 but never actually implemented in `rag/graph.py`).
**Files touched:** see B-005.
**Verification:** full 65/65 regression sweep across all five test
files, including a new test specifically targeting this bug that would
have failed against the pre-fix code.
**Still open:** the fixed version has NOT yet been run on real
hardware — only the original buggy version has real-world confirmation
so far. Next real run should re-test the same fusion-vs-fission-style
comparison query to confirm the fix actually finds better evidence on
retry, not just that the mechanics run without erroring.

### D-025 — Second real-hardware run exposed a second, worse retry bug (B-006)
**Phase:** 5, third real verification round
**Finding:** the same comparison query, re-run after D-024/B-005's fix,
proved the fix's mechanics worked exactly as designed (sub_queries
genuinely grew: 2 → 3 → 4 across attempts; evidence accumulated as
intended) — but the answer quality got worse, not better, because the
"refined" sub-query being added was raw prose (the sufficiency gap
explanation) sent verbatim to search APIs, not an actual search term.
See `debug.md` B-006 for the full root cause and fix.
**Pattern worth naming explicitly:** two real bugs in a row have now
come from the same underlying habit — treating a human-readable
explanation field as if it were usable machine input (B-005's version
reused `gap` as a retry signal at all without checking its shape; B-006
is the sharper version of the same mistake, reusing prose as a literal
API query string). The fix isn't just patching this instance — it's
splitting the schema so a prose field and a machine-usable field can
never be confused again, plus a structural length-based rejection as a
backstop rather than trusting a prompt instruction alone.
**Decision:** fixed per B-006. Not reverting D-024's core insight
(retries need to actually refine, not just repeat) — refining the fix
rather than abandoning the approach.
**Files touched:** see B-006.
**Verification:** 67/67 full regression sweep. Real-hardware
confirmation of THIS fix is still outstanding — same "verified in
sandbox, not yet on real hardware" gap as every fix in this thread so
far.

### D-026 — Third real-hardware run: B-006's fix was safe but silently inert on this local model
**Phase:** 5, fourth real verification round
**Finding:** re-running the same query with B-006's fix showed real
progress — no prose sentences sent as queries this time, confirming the
length-guard works. But sub_queries stayed at exactly 2 across all 3
attempts (no `[flags: ...]` line printed either), meaning the model was
returning an EMPTY `search_query` on this local Qwen3-4B setup despite
the prompt explicitly instructing it to always provide one when
insufficient. Net effect: retries were safe (no garbage sent) but
silently non-functional again — a quieter recurrence of B-005's
original problem, just without B-006's actively-harmful version.
**Decision:** rather than spend another full LLM call chasing better
prompt compliance (directly costly per D-022's accepted-but-real
per-call price), added a bounded, LLM-free fallback:
`_fallback_query_from_gap()` extracts keywords from the prose `gap`
field via simple stopword filtering, capped at the same 8-word limit
the primary path is validated against. Verified directly against the
actual `gap` text from this real run — it produces a genuinely usable
query ("recent progress fusion energy advances next-generation fission
reactor"), not a synthetic test fixture.
**Pattern continuation:** this is the third fix in a row on the same
retry-refinement mechanism (B-005 → B-006 → this). Each real run has
surfaced a real, different failure mode the prior fix didn't anticipate.
Noted plainly rather than treating "the tests are green" as sufficient
confidence at any point in this sequence — it wasn't, twice.
**Files touched:** `src/rag/sufficiency.py` (fallback function,
strengthened prompt with an explicit example and a "never leave
search_query empty" instruction), `test_phase5_manual.py` (new
regression test using the real-world gap text verbatim).
**Verification:** 68/68 full regression sweep. Real-hardware
confirmation of this fix specifically is, again, still outstanding.

### D-027 — Two modes (quick/deep) + spinner UI + verbose flag
**Phase:** UX feature, post-Phase 5
**Decision:** Added `--mode {quick,deep}` (default `deep`, preserving
all existing behavior unchanged) and `--verbose`/`-v` (default off).
**Quick mode, honestly scoped:** user asked for "responds in less than
30 seconds." Given this hardware's measured ~1.7-2 tok/s (D-022), a
single unconstrained LLM call routinely already takes 60-90+ seconds —
a hard <30s guarantee isn't achievable and I said so rather than
building something that silently fails to meet its own advertised
promise. What quick mode actually does: cuts the domain-gate LLM call
entirely (replaced by `core/domain_gate.py`'s new `quick_domain_check()`
— a heuristic pattern matcher, fails open to in-domain on anything not
clearly a coding/creative/roleplay request), always forces the fast
path regardless of the router's complexity classification (skips the
agentic path's multiple chained calls entirely), and caps output at 120
tokens (`QUICK_MODE_MAX_TOKENS`) vs deep mode's 512. This is "minimize
every avoidable cost," not "guarantee a time," and the CLI help text
and code comments say so explicitly rather than implying a promise.
**Spinner UI (`core/ui.py`, new):** a background-threaded single-line
spinner (`Spinner` class) that repaints one terminal line while blocking
LLM/retrieval calls run on the main thread, fully erased on exit — this
satisfies "remove any and all processing text when the final answer is
generated." `make_stage_reporter()` returns either a spinner-updating
callback (quiet/default) or a print-per-line callback (verbose) with the
same call signature, so `rag/graph.py` and `main.py`'s pipeline code
don't need to know which mode they're in — they just call `report(msg)`.
**`rag/graph.py` changed:** node closures now call an injected `report`
callback instead of hardcoded `print(..., file=sys.stderr)` — required
so the agentic path's stage updates also route through the spinner in
quiet mode, not just the fast path.
**Verbose mode preserves old behavior exactly:** one line per stage
(D-021/D-023's original design) plus live token streaming for the fast
path's synthesis call (streaming is NOT added to the agentic path in
this change — that gap, already noted in D-023, remains open).
**Quiet mode's output contract, per explicit user spec:** ONLY the
answer (which already embeds the "[Note: ...]" caveat text when the
retry cap was exhausted, per D-024's synthesis_node behavior), then the
sources block. No stage log, no flags, no timing — verbose mode is
where those live now.
**Files touched:** `src/core/ui.py` (new), `src/core/domain_gate.py`
(added `quick_domain_check()`), `src/rag/graph.py` (report callback
threading), `src/main.py` (full rewrite: mode/verbose flags, quiet-mode
spinner wiring, verbose-mode behavior preserved), `test_phase_modes_ui.py`
(new).
**Verification:** full regression sweep, 84/84 across all six test
files (13+11+17+16+11+16) — zero regressions from the `graph.py`/
`domain_gate.py` changes. New tests specifically confirm: quick-check
heuristics correctly distinguish coding/creative/roleplay requests from
research questions and fail open on ambiguous cases; the spinner thread
genuinely starts/stops and cleans up; both reporter modes wire correctly;
CLI argument defaults and shorthand flags parse correctly. Manually
re-verified the CLI's error paths (missing model, no query, `--help`)
still behave correctly after the full `main.py` rewrite. NOT yet
verified: an actual real-hardware run in both quick and verbose modes —
same pattern as every feature in this project so far, real confirmation
still needed before treating this as done.

### D-028 — First real-hardware run of the mode/UI feature: quiet mode confirmed correct, caught a real truncation bug myself
**Phase:** UX feature, first real verification
**Finding, positive:** ran all three modes (default quiet, `--mode
quick`, `--verbose`) on real hardware. Quiet mode worked exactly as
specified — only answer + sources printed, confirmed by direct contrast
with the `--verbose` run immediately after it showing the stage lines
that were correctly absent from the quiet run. Every citation across all
three runs resolved to a real listed source, zero fabricated IDs.
**Finding, a real bug caught before the user had to report it:**
quick mode's answer ended mid-word ("...The U") — `QUICK_MODE_MAX_TOKENS`
(120) cut generation off mid-sentence with no graceful handling, which
reads as broken output even though it's really just an unhandled
consequence of the hard cap.
**Fix:** added `rag/synthesis.py`'s `_smooth_truncation()` — if the raw
answer doesn't end on sentence-terminal punctuation, trim back to the
last complete sentence rather than showing a dangling fragment; if
there's no complete sentence at all (cut off very early), mark it
explicitly (`"[response cut short]"`) instead of silently presenting a
fragment as if it were the whole answer. Applied before citation
extraction, so a citation tag half-cut-off by truncation is never
included either.
**Scoping note, stated plainly:** this fixes the *returned* text (what
quiet mode shows, and what citation extraction operates on). It does
NOT retroactively fix `--verbose` mode's live token streaming — if
truncation happens there, the raw fragment was already printed to the
terminal character-by-character before smoothing could run. Acceptable
since verbose is explicitly the raw-debug view and the bug was actually
observed in quiet mode, where the fix fully applies.
**Files touched:** `src/rag/synthesis.py`, `test_phase4_manual.py`
(3 new regression tests, verified directly against the real truncated
and real complete text from this exact run, not synthetic fixtures).
**Verification:** 87/87 full regression sweep across all six test files.
Fix verified byte-for-byte against the real observed truncated output
(correctly drops "The U", preserves everything before it) and confirmed
a real complete answer passes through completely unchanged (zero risk
of the fix corrupting already-correct output).

### D-029 — B-008 closed for real; discovered latency has much higher variance than assumed
**Phase:** UX feature, second real-hardware confirmation
**B-008 closure:** re-ran quick mode twice more on real hardware — both
answers ended on complete, well-formed sentences with no truncation.
The fix is genuinely confirmed, not just passing synthetic tests.
**New finding, more important than the fix confirmation:** the same
`--verbose` command, same simple query ("What is fusion energy?"), same
machine, run immediately after two deep-mode runs that took 139.0s and
141.4s respectively, took **3277.0s (54.6 minutes)** — roughly a 23x
jump with no change in query, mode, or (per the user, asked directly)
anything externally unusual (no sleep/lock, no other heavy programs
running, nothing noticed).
**What this means:** every latency figure logged so far (D-022's 375.7s,
D-024 through D-026's ~250-450s range) was treated as a representative
baseline. It isn't -- it's one sample from a distribution with far more
spread than assumed. `trd.md` §6 updated to state this as a range with
high variance, not a point estimate, and to flag that the variance
itself is unexplained, not just the absolute speed.
**Root cause: NOT investigated further this session.** Real candidates,
none confirmed: Windows Defender real-time scanning intermittently
competing for CPU/disk during the model's large memory-mapped-turned-
resident (`use_mmap=False`, D-017) access pattern -- this was raised as
a hypothesis back in D-016 and never actually tested; OS-level
background tasks (Windows Update, search indexing) that wouldn't
register to the user as "a heavy program running"; intermittent thermal/
power-plan throttling not tied to a visible cause. Explicitly not
guessing further without a real measurement.
**Decision:** document the variance honestly rather than let it sit
silently contradicting the D-022 numbers already logged. Concrete,
low-effort next step for whenever this recurs: check Windows Task
Manager's Performance tab (CPU utilization, and specifically whether
"Windows Defender Antivirus Service" or similar shows sustained activity)
during a slow run, to actually gather evidence instead of guessing.
**Files touched:** `docs/trd.md` §6 (latency section revised to state
range + variance + open root-cause question, not a fixed baseline).
**Not treated as blocking:** per the established pattern (D-022's
explicit user choice to accept latency and proceed), this doesn't halt
further work -- it's logged so the next time someone is confused by a
wildly different timing number, the answer is "known, documented,
unexplained variance," not a new mystery each time.

### D-030 — Verbose mode simplified: same spinner UI, footer-only difference
**Phase:** UX feature, follow-up refinement
**Decision:** per direct user request, `--verbose` no longer prints a
per-stage log or streams tokens live during processing — it now uses
the exact same `Spinner`-based UI as default (quiet) mode. The only
remaining difference: after the same clean answer + sources output,
`--verbose` prints an extra diagnostic footer (flags, if any, and
elapsed time).
**Rationale beyond "user asked":** this also resolves a real technical
tension I hadn't flagged before — the old verbose design combined a
per-stage `print()` log with live token streaming to stdout, which
would have visually conflicted with a threaded spinner writing `\r`-
based updates to the same terminal if both were ever active together.
Unifying on one UI removes that latent conflict, not just satisfies the
request.
**Files touched:** `src/main.py` (module docstring, `--verbose` help
text, `main()` rewritten to a single shared code path with the footer
gated behind `args.verbose`).
**Verification:** 87/87 full regression sweep, zero regressions.
Manually re-confirmed `--help` text is accurate and the model-missing
error path is unaffected. NOT yet verified: an actual real-hardware run
of `--verbose` under the new behavior — same pattern as everything else,
needs real confirmation before treating this as done.

### D-031 — New sources: GitHub and Reddit added; X explicitly declined
**Phase:** tools extension (Phase 3 scope, not Phase 6)
**Decision:** added `tools/github_search.py` (GitHub REST search API,
unauthenticated, mandatory User-Agent) and `tools/reddit_search.py`
(Reddit's public `.json` search endpoint, unauthenticated, mandatory
User-Agent). Both added to `retriever_hybrid.py`'s default tool list —
an explicit, logged edit to the default set (per D-024's original note
that new tools shouldn't silently join by default).
**X/Twitter explicitly declined, not silently omitted:** X's API has
required a paid tier for search access since 2023 — directly conflicts
with `trd.md`'s "no API key required for core operation" constraint.
Scraping X is both fragile and against its ToS. Not built.
**Honesty note on Reddit specifically:** unlike GitHub's and arXiv's
official, documented public APIs, Reddit's `.json` endpoint is an
unofficial surface that happens to work without OAuth — flagged in the
module docstring as more fragile than the other three no-key sources,
not presented as equally durable.
**Files touched:** `src/tools/github_search.py` (new),
`src/tools/reddit_search.py` (new), `src/tools/__init__.py` (registers
both), `src/rag/retriever_hybrid.py` (default tool list).
**Verification:** parser logic tested against realistic fixture
payloads (not live endpoints, same sandbox limitation as every other
network tool) — 10/10 in `test_phase6_sources.py`, including edge cases
(null description, empty results) that wouldn't crash the parser.
Registration confirmed: all 6 tools now show up via `list_tools()`.
Live network calls NOT verified in this sandbox — same "needs a real
machine" pattern as `web_search`/`arxiv_feed`/`news_feed` originally.

### D-032 — Phase 6 started: citation_verifier, batched not per-claim
**Phase:** 6
**Decision:** built `verification/citation_verifier.py` — the per-claim
entailment check documented in `code_logic.md` §5 back when the graph
was first designed, but never actually implemented until now. Wired in
as a new `verification` node in `rag/graph.py`, after `synthesis`,
agentic path only — per the already-logged D-006 principle (heavy
verification spends budget only where multi-hop risk is highest, never
the fast path).
**The one implementation choice worth naming:** ALL claims from one
answer are batched into a SINGLE LLM call, not one call per claim. Given
this project's measured per-call cost (D-022's ~375s baseline, D-029's
much wider real variance), a per-claim verification loop would multiply
an already-expensive synthesis call by however many citations the
answer has — a fundamentally different, much worse cost profile than
one additional call. Verified directly: `test_phase6_manual.py`
confirms exactly one `model.chat()` call verifies two separate claims
together, not two calls.
**Fails open, consistent with every other classifier in this project:**
if the verifier's output can't be parsed, citations are returned
UNCHANGED (still `verified=None`), never guessed true or silently
marked passing. An already-known-bad citation (unresolved source_id,
set by `rag/synthesis.py` at parse time) is left alone rather than
re-checked — no reason to spend a call re-confirming something already
structurally known to be wrong.
**User-facing behavior:** if any citation fails entailment, the
agentic-path answer gets an appended caveat naming the count of
unverified citations — same pattern as the existing sufficiency-gap
caveat (D-024), not a silent pass/fail.
**Phase 6 scope note, stated honestly:** this implements ONE of Phase
6's three planned modules (`citation_verifier.py`). `answerability.py`
(pre-retrieval false-premise check) and `self_consistency.py`
(multi-sample variance check) from `phases.md`/`code_logic.md` are NOT
built yet — deliberately prioritized citation_verifier first as the
highest-value piece for a tool whose entire premise is grounded,
verifiable answers. Phase 6 is not being marked complete.
**Files touched:** `src/verification/citation_verifier.py` (new),
`src/rag/graph.py` (new `verification` node + import + edges),
`test_phase6_manual.py` (new), `test_phase5_graph.py` (updated stub
fixtures — every scripted synthesis reply now needs a matching
verification-stage reply, since the graph makes one more call per run).
**Verification:** 8/8 in `test_phase6_manual.py` covering mixed
verdicts, skip-already-known-bad, fail-open on unparseable output, and
the zero-citations no-op case. Full regression sweep across the entire
project: 105/105, zero regressions from wiring the new node into the
graph. NOT yet verified: an actual real-hardware agentic run exercising
the new verification node — same pattern as every feature in this
project, real confirmation still needed.

### D-033 — Real-hardware runs surfaced two real gaps: a D-030 side effect, and silent tool failures
**Phase:** 6 verification, Phase 5 (B-007) re-verification
**Finding 1, GitHub/Reddit query:** ran a real query expected to surface
GitHub/Reddit results. Neither appeared anywhere in the Sources list —
only web/news/arxiv results showed up. Root cause not yet determined
(could be legitimately zero relevant results, could be a silent
failure) BECAUSE `retriever_hybrid.retrieve()`'s bare
`except Exception: continue` gives zero visibility into which outcome
occurred — a real gap, not new behavior, just newly consequential now
that two more tools exist to fail silently.
**Finding 2, fusion-vs-fission query (B-007 re-test):** still couldn't
find fission-reactor sources, retrieved near-random arXiv results again
(LLM eval paper, graph-denoising paper) — the same symptom category as
B-006. Could NOT be diagnosed further because D-030 (simplifying
--verbose to match quiet mode) had an unintended side effect: it also
removed the sub_queries-list printing that let B-005/B-006/B-007 get
diagnosed in the first place. This was a real, unflagged regression in
debuggability, caught here rather than earlier.
**Decision:** added `--debug`, a new flag separate from `--verbose`,
restoring raw diagnostic visibility (sub_queries per retrieval attempt,
per-tool success/failure with exception detail, citation verification
counts) without reverting D-030's clean default UX. `--debug` disables
the spinner entirely rather than trying to interleave plain diagnostic
lines with a threaded `\r`-repainting spinner -- same visual-conflict
category D-030 already had to solve once for streaming vs. spinner, not
a new problem, just the same one recurring in a new spot. `--verbose`'s
footer still applies independently if both flags are given together.
Also threaded a `debug_report` callback into
`retriever_hybrid.retrieve()` itself, so a failing tool's exception
type and message are surfaced on request rather than only "0 chunks vs
some chunks" being distinguishable.
**Not yet resolved:** WHY the fusion-vs-fission query still fails, and
WHETHER GitHub/Reddit are actually broken -- both need a fresh run with
`--debug` to actually see the evidence, not another guess.
**Files touched:** `src/rag/retriever_hybrid.py` (`debug_report` param
+ exception surfacing), `src/rag/graph.py` (`debug_report` threaded
through `build_graph`/`run_agentic`, added to retrieval/sufficiency/
verification nodes), `src/main.py` (new `--debug` flag, spinner-bypass
branch), `test_phase5_graph.py` (stub `retrieve()` fixtures updated for
the new `debug_report` kwarg).
**Verification:** full regression sweep, 105/105, zero regressions.
NOT yet verified: an actual `--debug` run on real hardware — this whole
feature exists specifically because we don't yet have that evidence.

### D-034 — Real evidence from --debug: three distinct root causes, three distinct fixes
**Phase:** 6/tools, real evidence finally obtained
**Finding 1, Reddit — confirmed broken, not intermittent:**
`--debug` showed `reddit_search: FAILED -- HTTPError: 403 Client Error:
Blocked` on every single call, both queries, no exceptions. This is
structural, not flaky — Reddit is blocking unauthenticated requests
outright regardless of a descriptive User-Agent. D-031's caveat that
this endpoint was "more fragile than the others" turned out true
immediately, not eventually.
**Decision:** removed `reddit_search` from `retriever_hybrid.py`'s
default tool list. Module and registration left in place (opt-in via
explicit `tool_names`) in case Reddit's blocking behavior changes or an
OAuth-based approach gets built later — not deleted, just not spending
a doomed network round-trip on every query by default.
**Finding 2, GitHub — 0 results, not an error:** `github_search: 0
chunks` consistently, no failure. Root cause: sending full natural-
language question sentences to GitHub's keyword-oriented search API —
the same lesson as B-006, hitting a different tool this time.
**Decision:** added query simplification before the GitHub API call.
Rather than duplicate B-007's stopword-filtering logic a second time,
factored it out of `rag/sufficiency.py` into a new shared
`core/text_utils.py` (`simplify_to_keywords()`), used by both
`sufficiency.py` (unchanged behavior, now delegating to the shared
function) and the new `github_search.py` preprocessing step. Verified
directly against the real failing query: `"What are the latest open
source tools for LLM fine-tuning?"` → `"open tools llm fine-tuning"`.
**Finding 3, refined_search_query=None — NOT a logic bug:** traced the
exact real gap text from the debug output through the actual
`sufficiency_node()` code in this sandbox and got a correct, non-None
fallback result every time. The logic is right. Leading hypothesis: the
user's local `src/rag/sufficiency.py` is a stale file from before
D-026's fallback fix, likely because a zip re-extraction didn't
overwrite an already-present file. NOT YET CONFIRMED — a direct
verification step was handed to the user (grep their local file for the
fallback function) rather than asserting this as fact without checking.
**Files touched:** `src/core/text_utils.py` (new, shared keyword
extractor), `src/rag/sufficiency.py` (delegates to the shared function,
behavior unchanged, `_fallback_query_from_gap` kept as a named wrapper
so existing test imports still work), `src/tools/github_search.py`
(query simplification before the API call), `src/rag/retriever_hybrid.py`
(reddit_search removed from default list).
**Verification:** 105/105 full regression sweep, zero regressions from
removing reddit or refactoring the fallback logic. 5 new tests directly
covering `simplify_to_keywords()` (including against the exact real
failing query) and confirming reddit is out / github is still in the
default list.
**Still open:** whether Finding 3's stale-file hypothesis is correct —
needs the user's direct confirmation, not another guess from me.

### D-035 — Stale-file theory confirmed; real evidence of genuine fixes AND one new real bug
**Phase:** 5/6, real evidence finally complete
**Confirmed:** the stale-file hypothesis from D-034 was correct — after
a clean re-extraction, `grep` showed the D-026 fallback code present.
**Confirmed working, for real, not just in tests:**
- GitHub search (B-010 fix): 5 real chunks returned for the fine-tuning
  query (Axolotl/Unsloth/LLaMA-Factory repos, genuinely relevant).
- `citation_verifier` (Phase 6, D-032): ran on the agentic path and
  reported `2 verified, 0 unverified, 0 unchecked` — first real
  end-to-end confirmation this node functions correctly.
- B-007's primary fix path: attempt 1's sufficiency check produced a
  real, well-formed `refined_search_query='next-generation fission
  reactor advances 2026'` directly from the model, correctly appended
  to `sub_queries` for attempt 2. The mechanism genuinely works.
**New real bug found by this exact run (B-011):** attempt 2's
sufficiency check again showed `refined_search_query=None` despite a
non-empty `gap`. Traced in code, not guessed: the fallback logic's
`elif not sufficient and gap` branch was mutually exclusive with the
`if search_query:` (rejected-too-long) branch — so when the model
returned a search_query that was PRESENT but too long, it got rejected
and the code never tried the gap-based fallback at all. Only the
"search_query completely empty" case reached the fallback. Fixed by
restructuring to a single `usable_query` variable that's only left
`None` after BOTH the primary path and the fallback have failed, not
after the primary path alone.
**Also found via this run — real arXiv rate limiting, not a code bug in
the usual sense:** every arxiv_search call after the first failed, with
both `ReadTimeout` (arXiv itself being slow) and `HTTPError: 429`
(arXiv rate-limiting us) appearing across the run. Root cause: the
agentic path's multiple sub_queries × multiple retry attempts fires
several arxiv calls in quick succession with zero throttling — arXiv's
own documented guidance is roughly 1 request per 3 seconds, which
nothing in `arxiv_feed.py` was respecting.
**Fix:** added a simple module-level self-throttle to
`tools/arxiv_feed.py` (sleep if the last call was under 3s ago) and
raised the timeout from 10s to 20s (arXiv can genuinely be slow, not
just rate-limiting). Not a queue or backoff/retry system — just enough
to stop a single process hammering the endpoint.
**GitHub returning 0 results on the fusion/fission query, unlike the
5 it returned on the fine-tuning query — noted, not chased further:**
no `FAILED` entry (so not an error/rate-limit), most likely genuine
scarcity of GitHub repos matching an energy-policy topic vs. an
ML-tooling topic. Plausible, not confirmed; not worth more
investigation without further evidence it's actually a problem.
**Files touched:** `src/rag/sufficiency.py` (B-011 fix),
`src/tools/arxiv_feed.py` (throttle + timeout), `test_phase5_manual.py`
(new B-011 regression test verified against the exact real gap/
search_query text from this run; also fixed a test-authoring bug of my
own — passed a bare string to `StubModel` instead of a one-item list,
which `list()` silently iterated character-by-character).
**Verification:** 108/108 full regression sweep, zero regressions.
B-011's fix verified directly against the real gap and rejected
search_query text from this exact live run, not synthetic data.

### D-036 — B-011/B-012 fully confirmed; arXiv needed the same query-simplification fix as GitHub
**Phase:** 5/6, fourth real verification round
**B-011 confirmed:** the SECOND sufficiency check (previously always
`None`) now produced a real refined query
(`'progress fusion energy next-generation fission reactor designs'`),
correctly appended to `sub_queries`. This was exactly the broken case.
**B-012 confirmed:** every single `arxiv_search` call across both real
queries succeeded — zero `FAILED` entries anywhere in the run, versus
multiple 429s/timeouts before the throttle fix.
**New finding, same root cause as B-010, unapplied to a second tool:**
despite real, well-formed sub-queries and successful arXiv calls, the
returned papers were still irrelevant (video forensics, heavy-ion
collision physics, group recommendation) — `arxiv_feed.py` never got
the keyword-simplification treatment `github_search.py` did (B-010). It
was still sending full natural-language sentences into arXiv's `all:`
search, which does loose term-matching. Fixed identically to B-010:
`simplify_to_keywords()` applied before the query is sent. Verified
directly against the exact real sub-query text from this run.
**Separately noted, NOT fixed this turn:** the model wrote
`[arxiv:2, arxiv:3]` as one bracket with two comma-separated IDs — our
citation regex only matches single clean IDs per bracket, so it
extracted zero citations from a sentence that referenced two real
sources. Does not compromise safety (nothing false was marked grounded,
it just under-counted), but it's a real parsing gap. Deliberately
deferred rather than silently expanded scope — flagged here so it isn't
lost, not treated as urgent since it doesn't cause incorrect grounding.
**Files touched:** `src/tools/arxiv_feed.py`, `test_phase6_sources.py`.
**Verification:** 113/113 full regression sweep. Simplification tested
directly against the real sub-query text from this exact live run.
Live network re-confirmation of the actual result relevance still
needed — sandbox can verify the query transformation, not whether
arXiv's results genuinely improve.

### D-037 — B-013's fix confirmed deployed but insufficient; deeper root cause found by cloning the real repo
**Phase:** 6/tools, fifth real verification round
**Finding:** re-ran the fusion-vs-fission query after B-013's fix —
arXiv results were STILL irrelevant, byte-for-byte the same failure
pattern as before. Rather than assume a stale file again, cloned the
actual live GitHub repo directly (`git clone` — allowed network domain
in this sandbox) and confirmed the B-013 fix genuinely is deployed,
correct, matching what was written. So the fix works as designed but
doesn't solve the actual problem — a different, deeper bug.
**Real root cause:** `arxiv_feed.py` was sorting by
`sortBy="submittedDate"` (most recent first), not relevance. arXiv's
`all:` field does loose/broad term matching, not strict AND — so
sorting those loose matches by recency instead of relevance surfaces
the NEWEST paper that shares even one stray word with the query, not
the most topically relevant one. This is architecturally distinct from
B-013 (query phrasing) — B-013 was a real, correct fix for a real
problem, it just wasn't the ONLY problem.
**Fix:** changed to `sortBy="relevance"`. Recency isn't lost — it's
already handled downstream by `rag/reranker.py`'s `requires_recency`
boost (built back in Phase 3/D-019), so sorting arXiv itself by
relevance and letting the reranker apply recency weighting afterward is
the correct division of responsibility, not a regression against
`prd.md`'s freshness requirement.
**Correction to my own error in this same turn:** I initially claimed
`github_search.py` was missing from the cloned repo based on a
misread `find` output — direct `ls` immediately after showed it was
present and correct. Stated here so the record doesn't carry a false
claim uncorrected.
**Process note, not a bug:** the user's single commit
(`"Fix arXiv result relevance with query simplification"`) actually
contains all of D-027 through D-036 (54 files) — the message
undersells its own contents. Not fixed in code, just noted for future
commits to follow the split convention from `workflow.md` §7 rather
than one large squash.
**Files touched:** `src/tools/arxiv_feed.py`.
**Verification:** 113/113 full regression sweep, zero regressions.
Verified the actual deployed code by cloning the real repository
directly rather than asking the user to grep locally — a more reliable
verification method than prior rounds, now established for future use
if this class of confusion recurs.

### D-038 — B-014 confirmed working; found and fixed a real source_id collision bug (B-015)
**Phase:** 6, sixth real verification round
**B-014 confirmed:** the fine-tuning query returned a fully coherent,
well-grounded answer citing 5 valid GitHub repos plus web sources. The
fusion/fission query's arXiv calls all succeeded, though this
particular run's final answer happened to cite no arXiv sources at all
(not itself concerning — depends on what actually ranked highest).
**New finding: literal source_id collision, spotted directly in the
Sources output** — `[news:0]` appeared twice, pointing to two
completely different real articles. Traced to a real, previously
unnoticed bug: every individual tool module (`tools/news_feed.py`, etc.)
numbers its own results starting at 0 per call. The fast path only ever
calls `retrieve()` once, so this never surfaces there — but the agentic
path accumulates results across multiple sub_queries AND multiple retry
attempts (`rag/graph.py`'s `retrieval_node`), and `dedupe()` only checks
`(source, content)` uniqueness, never `source_id`. Two genuinely
different chunks from different `retrieve()` calls can end up sharing a
literal ID.
**Why this matters beyond display confusion:** `verification/
citation_verifier.py` builds `{c["source_id"]: c for c in chunks}` — a
dict, so a collision silently shadows one of the two chunks. A citation
could be checked against the WRONG source's text entirely. This is a
plausible real explanation for this exact run's "1 unverified" citation,
though not confirmed as the specific cause without deeper tracing —
stated as plausible, not certain.
**Fix:** added `renumber_source_ids()` to `rag/retriever_hybrid.py`,
called right after `dedupe()` in `retrieval_node` — reassigns every
chunk a fresh, globally-unique ID within the accumulated list, preserving
the original type prefix (`news:`, `web:`, etc.) for readability. Not
applied to the fast path, which doesn't need it (single `retrieve()`
call, no accumulation, no collision risk).
**Files touched:** `src/rag/retriever_hybrid.py`, `src/rag/graph.py`,
`test_phase5_graph.py`.
**Verification:** reproduced the EXACT real collision (two chunks both
"news:0", different content) directly and confirmed the fix resolves it
(`news:0`/`news:1`). Added a properly targeted regression test using a
retrieve stub that resets its ID counter every call (mimicking real
tool behavior) — the earlier accumulation test's stub used a global
counter and never actually exercised this bug, worth noting as a gap in
my own prior test design, not just the code. 116/116 full regression
sweep.

### D-039 — B-015 confirmed fixed; found and fixed a common citation-undercounting bug (B-016)
**Phase:** 6, seventh real verification round
**B-015 confirmed:** the re-run's final Sources list had zero duplicate
IDs anywhere. Closed for real this time.
**New finding, from checking the citation math, not just reading the
answer:** the model cited `[web:0][web:1][web:2]` — three tags — but
`citations: 0 verified, 1 unverified, 0 unchecked` only accounted for
ONE citation total. Traced directly: `_extract_citations()`'s claim-
text-between-tags logic requires non-empty text between every pair of
adjacent tags, and back-to-back tags (a common, normal pattern for
multi-citing one claim) have nothing between them — `if not claim_text:
continue` silently dropped every tag after the first in any such run.
**Fix:** `_extract_citations()` now tracks the last non-empty claim
text and reuses it for adjacent tags, instead of dropping them. Only
skips a tag when NO claim text has ever appeared yet (a genuine edge
case — an answer opening with a citation before any prose).
**Files touched:** `src/rag/synthesis.py`, `test_phase4_manual.py`
(3 new tests: the exact real 3-tag case, confirming shared claim text
across adjacent tags, and confirming the genuine leading-citation edge
case still correctly skips).
**Verification:** tested directly against the real answer text from
this run — 3/3 citations now extracted where only 1 was before, byte-
identical to the live failure. 119/119 full regression sweep.
**Note:** this is a more common, higher-impact pattern than the earlier
comma-in-one-bracket gap (`[arxiv:2, arxiv:3]`) noted and deliberately
deferred — that one remains open, unfixed, low-priority. This one was
worth fixing immediately since multi-citing one claim with adjacent
tags is normal model behavior, not a rare formatting quirk.

### D-040 — Comma-in-bracket citation format recurred in real usage; fixed with the same B-016 mechanism
**Phase:** 6, clean (non-debug) real run
**Finding:** a clean `main.py` run (no `--debug`) showed
`[web:0, web:1]` — the comma-separated-IDs-in-one-bracket pattern
noted and deliberately deferred back in Entry 021. Recurring in real
usage (not hypothetical) was the trigger to fix it now rather than
keep deferring.
**Fix:** extended `_CITATION_TAG_PATTERN` to allow comma/whitespace
inside a bracket, then split each match's contents on comma into one
citation per ID, reusing B-016's last-claim-text mechanism so all IDs
from one bracket share the same claim attribution.
**Also confirmed NOT a bug:** the same run showed `[news:15]` next to
`[news:0]`/`[news:1]` in the Sources list, which looked suspicious at
a glance. Traced through: this is B-015's renumbering working
correctly — 3 retry attempts accumulated 15+ distinct news chunks,
uniquely renumbered across the whole session, then curator/reranker
filtered down to 3 survivors with non-contiguous but still unique
indices. B-015 guarantees uniqueness, not contiguity — gaps are
expected whenever most of a renumbered set gets filtered out.
**Files touched:** `src/rag/synthesis.py`, `test_phase4_manual.py`.
**Verification:** tested directly against the real answer text from
this run — 2/2 citations now extracted where 0 were before (the old
regex didn't match a comma-containing bracket at all). 121/121 full
regression sweep.

### D-041 — Phase 7: short-term conversation memory, context scoped to synthesis only
**Phase:** 7
**Decision:** built `memory/conversation_buffer.py`'s `ConversationBuffer`
(bounded to `MAX_TURNS=6`, single-session, in-memory only — no
persistence across process restarts, that's `architecture.md`'s
`long_term_store.py` v2 extension point, not this) and a new `--chat`
interactive mode in `main.py` (`run_chat_loop()`).
**The one design choice that actually matters here:** conversation
context is threaded into `rag/synthesis.py`'s `generate()` ONLY —
never into the query used for `core/domain_gate.py`, `core/router.py`,
or `rag/retriever_hybrid.py`'s `retrieve()`. Reasoning worked out before
writing code, not discovered by a failed test: `router.py`'s complexity
classifier uses a 25-word threshold — prepending prior Q&A to every
follow-up would push nearly all of them over that line, misrouting
simple follow-ups into the expensive agentic path every time. It would
also pollute retrieval search terms with old-topic keywords, degrading
result relevance for the actual current question. Keeping
`domain_gate`/`router`/`retrieval` on the raw follow-up text and only
enriching the final synthesis call (where the model actually needs to
resolve references like "that" or "the second one") avoids both
problems entirely.
**Files touched:** `src/memory/conversation_buffer.py` (new),
`src/rag/synthesis.py` (`generate()` gained `conversation_context`
param), `src/rag/graph.py` (`build_graph()`/`run_agentic()` thread it
through to the agentic path's synthesis node too, so both paths
benefit), `src/main.py` (`run_query()` threads it through, new
`--chat` flag + `run_chat_loop()`), `test_phase7_manual.py` (new).
**Verification:** 136/136 full regression sweep across all 9 test
files. New tests confirm: buffer add/format/trim/clear behavior, the
`MAX_TURNS` bound is respected, long answers get truncated in the
formatted context (not included in full), and — the test that actually
matters most — `generate()`'s real prompt sent to the model contains
the injected context when given, and contains no context block at all
when `conversation_context=""`. Manually re-confirmed by reading
`run_query()`'s full body that `state = new_state(query)` and every
`check_domain`/`route`/`retrieve` call use the raw `query`, never an
enriched one. NOT yet verified: an actual real-hardware `--chat`
session — same pattern as every feature in this project, needs real
confirmation before treating this as done.

### D-042 — Phase 7 confirmed working on real hardware, first try, no bugs
**Phase:** 7, real verification
**Finding:** first `--chat` session confirmed the exact scenario Phase
7 was built for. Turn 1: "What is fusion energy?" — clean, grounded
answer, valid citations. Turn 2: "How does that compare to fission?" —
retrieval correctly used the raw follow-up (no context pollution,
"fission"/"compare" alone were enough keywords to pull genuinely
on-topic sources like NRC's and DOE's fission-vs-fusion pages), and
synthesis correctly resolved "that" to mean fusion energy using the
injected conversation context, producing a coherent comparison rather
than answering as if "that" were undefined. Both turns' citations
resolved to real, listed sources with no duplicates and no dropped
citations.
**Why this validates D-041's design call specifically:** the
raw-query-for-retrieval decision wasn't just theoretically sound, it
worked in practice on the first real test — retrieval didn't need
context injection to find the right sources for a pronoun-laden
follow-up, because the follow-up's own real keywords were sufficient.
**No bugs found, no fixes needed.** Noted here as a clean success,
not left unrecorded just because nothing broke — a real confirmation is
still worth logging with the same rigor as a bug.

### D-043 — Phase 8: PyInstaller packaging built, mechanics verified in sandbox, real main.py build still needed
**Phase:** 8
**Decision:** built `build/_common.py` (shared invocation logic —
avoids triplicating the same PyInstaller command across three
per-OS scripts), `build/build_windows.py`, `build/build_macos.py`,
`build/build_linux.py` (each a thin OS-specific entry point calling
the shared function), `build/hooks/hook-llama_cpp.py` (the required
hook flagged as a known landmine back when packaging was first scoped
— llama-cpp-python's compiled shared library isn't visible to
PyInstaller's default import scanner without it), and
`build/requirements-build.txt` (PyInstaller kept separate from the
main runtime `requirements.txt`, since packaging tooling isn't needed
to just run Fathom).
**`--onedir`, not `--onefile`:** a `--onefile` build re-extracts itself
into a temp directory on every single launch, adding real latency to
every invocation, not just the first. `--onedir` pays that cost once,
at install/unzip time. Worth doing even though this app's own per-query
latency (D-022) already dwarfs a few seconds of unpack time — no reason
to add avoidable overhead on top of an already-accepted one.
**What was actually verified in this sandbox, and how:** installed
PyInstaller directly (fast — unlike `llama-cpp-python`, no slow native
build) and ran the real invocation mechanics from `_common.py` against
a minimal stand-in script (not the real `main.py`, which needs
`llama-cpp-python` — untestable here per the standing sandbox
limitation, same as every other llama-cpp-python interaction in this
project). Confirmed: the build completes successfully, produces a
working standalone executable that runs independent of the Python
interpreter/venv, and — importantly — passing `--additional-hooks-dir`
at our real `build/hooks/` directory causes no error even when the
hooked module isn't imported by the built script, confirming the hook
mechanism itself won't break the real build.
**What remains genuinely unverified, stated plainly:** the actual real
`main.py` build (needs `llama-cpp-python`, can't be built in this
sandbox), whether the hook correctly bundles the compiled library when
it's actually needed, and all cross-platform builds (this sandbox is
Linux-only — Windows/macOS builds need to run on those OSes per D-005,
can't be tested here at all).
**Files touched:** `build/_common.py`, `build/build_windows.py`,
`build/build_macos.py`, `build/build_linux.py`,
`build/hooks/hook-llama_cpp.py`, `build/requirements-build.txt`.
**Verification:** real PyInstaller build + real executable run,
confirmed in this sandbox with a stand-in script (see above for exact
scope). Real `main.py` build on real hardware is the next, necessary
step — same "sandbox confirms what it can, real hardware confirms the
rest" pattern as everything else in this project.

### D-044 — Phase 8 (Windows) CONFIRMED WORKING END-TO-END on real hardware
**Phase:** 8, real verification
**Finding:** built `fathom.exe` from the real `main.py` (not a
stand-in) on real Windows hardware. Build log confirmed
`hook-llama_cpp.py` fired correctly and `llama_cpp\lib` was picked up
in the DLL search path — the exact mechanism D-043 flagged as needing
real-hardware confirmation. Then the `.exe` was actually run, standalone,
from a plain terminal with no Python venv active — loaded the real
model, retrieved real live sources, produced a correctly grounded
answer with every citation resolving to a real listed source. This is
the genuine end-to-end confirmation Phase 8 needed, not just a
successful build log.
**Windows target: DONE.** macOS and Linux builds remain untested — per
D-005, PyInstaller can't cross-compile, so each needs to be built and
run on that actual OS separately. Not assumed to work just because
Windows did.
**Minor, non-actionable observation:** the answer had two missing-space
typos ("theextreme," "bythe"). Confirmed this is a model generation
quirk, not a packaging or citation-pipeline bug — nothing in Fathom's
own code touches whitespace in the raw generated text. Not fixing;
noted so it isn't mistaken for a regression later.
**Files touched:** none — this is a verification-only entry.
**Verification:** real build + real standalone execution + real
grounded, correctly-cited answer, all on real Windows hardware.

### D-045 — Phase 6 completed: `answerability.py` + `self_consistency.py` built and wired
**Phase:** 6
**Finding/Decision:** built the two remaining Phase 6 modules per
`code_logic.md` §6/§7 and wired them into both paths.

`verification/answerability.py` mirrors `core/domain_gate.py`'s shape
exactly (cheap single classifier call, `CONFIDENCE_THRESHOLD=0.6`,
fail-open to "answerable, flagged" on parse failure, never a silent
unflagged pass and never an unwarranted refusal on a parsing hiccup).
Unlike `citation_verifier.py` (a HEAVY call, agentic-only per
D-006/D-032), this check is cheap enough to run on both paths, matching
`code_logic.md` §3's placement (before synthesis) and §6's "runs both
pre-retrieval and post-retrieval on the agentic path" spec:
- **Agentic path** (`rag/graph.py`): new `answerability_pre` node runs
  BEFORE `planner` -- a definite false-premise hit here skips
  planning/retrieval/curation/sufficiency/synthesis entirely (routed
  straight to `END` via a new conditional edge), since this is the one
  place catching the problem early actually saves real cost rather than
  just adding a caveat after the fact. The existing `verification` node
  (after `synthesis`) gets a second, evidence-aware re-check per
  `code_logic.md`'s "re-checked here for agentic multi-hop drift" --
  this one CAVEATS the existing answer rather than discarding
  already-paid-for synthesis work.
- **Fast path** (`main.py`): one evidence-aware check after rerank,
  before synthesis, matching `code_logic.md` §3 step 3 exactly. Skipped
  entirely in `--mode quick` -- quick mode's whole purpose (D-027) is
  minimizing LLM calls, and this is exactly the kind of extra call that
  mode exists to avoid; deep mode pays it since deep mode's stated
  priority is accuracy over latency. A definite-failure verdict returns
  early (same pattern as the existing domain-refusal branch just above
  it), bypassing `output_rail` entirely -- routing it through
  `output_rail`'s `require_citations` check would have rejected the
  citation-free refusal message and silently replaced it with the
  generic failure text instead.

`verification/self_consistency.py`: agentic-path only, per
`code_logic.md` §4 ("if agentic_path: self_consistency..."), wired into
the same `verification` node. Resamples synthesis at
`SAMPLE_TEMPERATURE=0.7` (higher than synthesis's default 0.3 --
deliberately, so genuinely uncertain claims have room to actually vary;
low-temperature resampling would make every sample nearly identical
regardless of underlying uncertainty and defeat the check's purpose).
Extracts a bounded, dependency-free "fact" set per sample (numbers/
percentages, years, capitalized multi-word entities via regex -- same
"cheap heuristic beats an NLP dependency we can't afford" philosophy as
`core/text_utils.py`, given `trd.md` §1's CPU/<6GB constraint) and flags
any fact from the primary answer not corroborated by every resample.

**Explicit cost tradeoff, stated plainly (not buried):** self-consistency
adds a full EXTRA synthesis call to every agentic-path query. Given this
project's own measured per-call latency (D-022: ~140-3277s, cause of the
variance still unresolved per D-029), this is real, uncertain latency
added by default, not a cheap check. Mitigations: `N_SAMPLES=2` (the
observable minimum -- one extra call, not the 2-3 `code_logic.md` §7
allows for), and a new `enable_self_consistency` parameter threaded
through `build_graph()`/`run_agentic()` so this can be disabled without
a code change once real-hardware timing data for it specifically exists.
Recommend real-hardware confirmation treats this as its own timing
question, not folded into the existing latency backlog.

`rag/synthesis.generate()` gained a `temperature: float = 0.3` parameter
(default unchanged, every existing caller behaves identically) so
`self_consistency.py` can request a resample without duplicating the
whole function.

**Doc-consistency note** (per `workflow.md` §5): `code_logic.md` §3 step
5 describes `citation_verifier.check(answer, results)` as a "structural:
tag present + ID resolves" check running on the fast path -- but that
structural check is actually already implemented elsewhere
(`rag/synthesis._extract_citations` + `core/guardrail.output_rail`), and
the real `citation_verifier.py` module is a HEAVY LLM entailment call,
deliberately agentic-only per D-006/D-032. This mismatch predates this
session's work and wasn't introduced or fixed here -- flagging it now
per the conflict-resolution rule (favor `decisions.md` over
`code_logic.md` convenience) rather than silently leaving it
undocumented. `code_logic.md` §3 step 5's wording should be corrected in
a future doc-only pass to describe the structural check that actually
runs on the fast path, without implying `citation_verifier.py` itself
runs there.
**Files touched:** `src/verification/answerability.py` (new),
`src/verification/self_consistency.py` (new), `src/rag/graph.py`,
`src/rag/synthesis.py`, `src/main.py`, `test_phase5_graph.py` (updated
scripted-reply sequences for the two new model calls per graph run,
`enable_self_consistency=False` added since that suite tests retry-loop
logic, not verification), `test_phase6_answerability.py` (new),
`test_phase6_self_consistency.py` (new), `test_phase6_graph_wiring.py`
(new -- covers the `answerability_pre` short-circuit, the ambiguous
pass-through case, and self-consistency's flag-on-divergence and
disable-via-flag behavior directly against the compiled graph).
**Verification:** 180/180 across the full 12-file regression sweep
(stub-model based -- this sandbox still can't load the real GGUF model,
same standing limitation as every other phase). NOT yet verified: real
model + real hardware, same gap as every phase before real-hardware
confirmation happens.
**Phase 6 exit criteria met?** Code-complete: all three planned modules
now exist and are wired (`citation_verifier.py` was already confirmed
working; `answerability.py` and `self_consistency.py` are new this
session). Per-claim citation accuracy metric (`trd.md` §7) still needs
real eval-set tracking, not just unit-level confirmation -- that's a
distinct, still-open piece of Phase 6's exit criteria, not resolved by
this session's work alone.

---

### D-046 — `self_consistency` cost tradeoff resolved: default flipped to OFF; `code_logic.md` corrected
**Phase:** 6, follow-up to D-045
**Finding/Decision:** D-045 shipped `enable_self_consistency` defaulting
to `True` (matching `code_logic.md` §7's spec) while simultaneously
flagging, unresolved, that this adds a full extra synthesis call to
every agentic query against an already-uncertain per-call latency
profile (D-022/D-029: ~140-3277s, cause of variance still unresolved).
Leaving a known, unmeasured cost defaulted ON and calling it "flagged"
was not actually a resolution -- it deferred the decision while still
shipping the more expensive behavior by default. Fixing that now:
`enable_self_consistency` defaults to **False** in both
`build_graph()` and `run_agentic()` (`rag/graph.py`). `main.py`'s
agentic-path call site left at the default (with an inline comment
explaining why), rather than passed explicitly, so flipping the default
back once real-hardware timing data exists doesn't require touching
`main.py` at all.

Also corrected `code_logic.md` §3 step 5, which mislabeled a fast-path
structural citation check as `citation_verifier.check()` (flagged as a
pre-existing doc inconsistency in D-045, not fixed there) -- it now
correctly attributes that structural check to `guardrail.output_rail`,
with an explicit note that `citation_verifier.py` itself is the
separate, heavy, agentic-only entailment call. `code_logic.md` §7 also
updated to state the actual implemented sampling temperature (0.7, not
"low temperature" as originally sketched) and to document the new
default explicitly, so the spec doc matches the shipped code rather
than the other way around.

**Self-inflicted bug caught and fixed in the same pass:** the
`str_replace` that changed `build_graph()`'s default from `True` to
`False` dropped the function signature's closing `):` in the
replacement text, breaking `rag/graph.py` with a `SyntaxError: '(' was
never closed`. Caught immediately by re-running the regression suite
(the correct discipline here, not by re-reading the diff and assuming
it was fine) — fixed by restoring the closing `):` before the
docstring. Not logged as a numbered `B-XXX` bug since it never reached
a committed state; call it out here for the record rather than pretend
the first edit was clean.
**Files touched:** `src/rag/graph.py`, `src/main.py`, `docs/code_logic.md`.
**Verification:** 180/180 across the full 12-file regression suite,
confirmed AFTER fixing the syntax error above (the sweep is what
caught it).
**Still open:** the same real-hardware timing gap D-045 named --
nothing about this follow-up changes that. `self_consistency` remains
implemented and testable, just off by default until it's actually been
timed on real hardware.

### D-047 — `--self-consistency` CLI flag added, for the real-hardware confirmation D-045/D-046 called for
**Phase:** 6, follow-up to D-045/D-046
**Finding/Decision:** D-046 flipped `enable_self_consistency`'s default
to `False` but left it only settable from Python code, not from the
CLI -- meaning the real-hardware timing run both D-045 and D-046
explicitly called for had no way to actually turn the feature on
without editing source. Added `--self-consistency` to `build_parser()`
and threaded it through `run_query()` into `run_agentic()`. No default
change (still off unless passed) -- this is purely closing the gap
between "the flag exists in code" and "a person on real hardware can
exercise it."
**Files touched:** `src/main.py`.
**Verification:** 180/180 regression sweep, unchanged behavior when the
flag isn't passed (confirmed by the existing suite, none of which pass
it). The flag itself needs real-hardware exercise, same standing gap
as everything else in Phase 6 -- see status.md's testing commands.

### D-048 — Per-claim citation accuracy metric established and tracked (`trd.md` §7 / Phase 6 exit criteria)
**Phase:** 6, closing the one remaining exit-criteria item
**Finding/Decision:** built `tests/eval/citation_accuracy_eval.py`, a
Phase-6-scoped eval harness -- deliberately NOT Phase 10's full
`golden_set.jsonl` suite (see `tests/eval/README.md` for the scope
split, added to prevent this file from later being confused with or
duplicated by Phase 10's work). Metric definition:

    accuracy = verified / (verified + unverified)

computed from `verification/citation_verifier.py`'s own entailment
verdicts, aggregated across every citation produced by
`tests/eval/phase6_citation_queries.jsonl`'s 12 queries run through the
REAL agentic path (`run_agentic()` called directly, bypassing the
router -- `citation_verifier` is agentic-path-only per D-006/D-032, so
forcing that path is the only way to get a signal at all). `unchecked`
citations are tracked and reported separately, never folded into the
accuracy ratio -- an unresolved verdict is neither a confirmed pass nor
a confirmed failure, and counting it as either would misrepresent what
was actually checked. A single query's exception (e.g. a retrieval tool
failing) is caught and recorded rather than aborting the whole run, so
one bad query doesn't discard every other query's real signal.

`append_to_log()` writes one dated entry per run to the new
`docs/eval_log.md`, never overwriting prior entries -- this is what
makes the metric "tracked" per `phases.md`'s exit-criteria wording
(established AND tracked), not just computable once and forgotten.
That file deliberately has no `Return to /context.md` trailer, unlike
every other `/docs/*.md` file -- since entries are appended
automatically, a trailer would end up sandwiched mid-file after the
first real run rather than staying at the true end.

**What this does and does NOT close:** this establishes the metric and
the tracking mechanism, and validates its arithmetic/aggregation logic
end-to-end against a stub model (same "sandbox confirms mechanics, real
hardware confirms substance" split as every other phase in this
project -- see `test_phase6_citation_eval_harness.py`, 18/18 passing).
It does NOT produce a real number -- this sandbox has no real model and
no access to the retrieval tools' external APIs (web search etc. are
outside the network allowlist here), so an actual accuracy figure can
only come from running `python tests/eval/citation_accuracy_eval.py` on
real hardware. `docs/eval_log.md` explicitly says no real entry has
been logged yet, rather than implying this is done.
**Files touched:** `tests/eval/README.md` (new), `tests/eval/
citation_accuracy_eval.py` (new), `tests/eval/
phase6_citation_queries.jsonl` (new, 12 queries), `docs/eval_log.md`
(new), `test_phase6_citation_eval_harness.py` (new, sandbox validation).
**Verification:** 198/198 across the full 13-file regression sweep.
**Still open:** the actual real-hardware run and its resulting number
-- same standing gap named in D-045/D-046/D-047 and status.md's current
"on hold" note. This decision closes the MECHANISM gap in Phase 6's
exit criteria, not the DATA gap; both were real, and only the first is
fixed here.

### D-049 — Judge model for Phase 10 eval: separate offline open-source model, NOT Qwen3-4B, NOT a hosted API
**Phase:** 10 (design decision only — logged ahead of implementation
per the same precedent as D-001 anticipating Phase 6; NOT started as
code, since `phases.md`'s ordering rule means Phase 10 shouldn't be
built until Phase 6/8 close, and both are still open per status.md
Entry 030/031's "on hold" state)
**Finding/Decision:** discussed three options for Phase 10's offline
eval judge (`trd.md` §7's "Ragas/Langfuse-style scoring"): (1) reuse
Qwen3-4B itself, (2) a hosted API judge (GPT-4/Claude-class), (3) a
separate offline open-source model. User chose (3), explicitly ruling
out both self-judging and any hosted API dependency.

**Why not Qwen3-4B as its own judge:** self-preference bias and
correlated blind spots are well-documented failure modes when a
model judges its own output -- here that risk is maximal, not just
"same family," since generator and judge would be the literal same
weights. A systematic weakness in Qwen3-4B (e.g. subtle numeric or
date handling) would affect both the answer AND the judgment of that
answer identically, since the same limitation produces both. This
exact risk already exists at RUNTIME in `citation_verifier.py`
(D-006/D-032) -- an accepted tradeoff there because the alternative
was a hosted API in the shipped product, which `trd.md` §8 explicitly
excludes from v1. Phase 10's eval doesn't ship to end users, so that
constraint doesn't force the same tradeoff here.

**Why not a hosted API:** ruled out explicitly by the user. Would
have been the literature's more common choice (Ragas etc. typically
assume a frontier hosted judge), but introduces a first-ever external
API dependency into a codebase that currently has none, plus ongoing
cost, key management, and a risk of the judge silently changing
behavior on a provider-side model update between eval runs months
apart.

**Chosen: Llama-3.1-8B-Instruct, GGUF, Q4_K_M quant (~4.9GB).**
- Different training lineage from Qwen (Meta vs. Alibaba) -- this
  matters more for reducing self-preference/correlated-bias risk than
  raw size alone; two same-family models can share blind spots even
  at different scales.
- Fits the user's stated constraint (same <6GB-class machine Fathom's
  own model runs on) -- loaded SEQUENTIALLY at eval time (generate
  with Qwen3-4B, unload, load the judge to score), never concurrently,
  so peak memory never exceeds what one model alone needs.
- Zero new infra: same `llama-cpp-python` + `core/llm_backend.py`
  loading pattern already in the codebase for Qwen3-4B. No new
  dependency, no API keys to keep out of `build/`'s packaged output.
- 8B vs. 4B gives real headroom specifically for judgment tasks
  (entailment, subtle factual drift) that benefit more from capacity
  than generation does.

**Not yet decided / explicitly deferred:** exact quantization variant
beyond Q4_K_M, download/checksum mechanism for the judge model (likely
reuses whatever `installer_support/model_downloader.py` builds for
Phase 9, once that exists), and how `citation_accuracy_eval.py`
(D-048) gets extended to optionally score with this judge alongside
or instead of `citation_verifier.py`'s existing self-judged verdicts.
None of this is implemented -- this entry exists so the decision isn't
re-litigated when Phase 10 actually starts.
**Files touched:** none (design-only).
**Verification:** N/A -- no code to verify yet.
**Still open:** Phase 6 and Phase 8 still need to close before any of
this gets built, per `phases.md`'s ordering rule -- this decision is
ready to implement the moment they do, not a signal to start now.

### D-050 — D-049 implemented ahead of schedule, at explicit user request; ordering-rule exception, not a repeal
**Phase:** 10 code, written while Phase 6/8 are still open
**Finding/Decision:** D-049 said explicitly "this decision is ready to
implement the moment they do, not a signal to start now." The user
then asked directly for the code and runnable commands anyway. This is
logged as a deliberate, explicit exception made at the project owner's
request -- not a quiet reversal of `phases.md`'s ordering rule, and not
a precedent for skipping it again without being asked. Phase 6 and
Phase 8 are STILL open; nothing about writing this code changes that,
and this code does not get treated as "Phase 10 is now underway" for
scheduling purposes.

**Built:**
- `tests/eval/judge_model.py` — `JudgeModel`, mirroring
  `core/llm_backend.FathomModel`'s `chat()` signature exactly (so it's
  a drop-in for anywhere a `FathomModel` is accepted, specifically
  `citation_verifier.verify_citations()`, without touching that
  function at all). Deliberately kept under `tests/eval/`, never
  imported from anything under `src/` -- this must never end up bundled
  into `build/`'s PyInstaller output (Phase 8). Separate model
  directory (`~/.fathom/eval-judge-models/`) and separate env var
  (`FATHOM_JUDGE_MODEL_PATH`) from the production model, so the two can
  never collide or be mistaken for each other.
- `tests/eval/citation_accuracy_eval.py` extended with
  `run_eval_with_judge()` (both models pre-loaded, for testing) and
  `main_with_judge()` (the real CLI path: loads Qwen3-4B, runs every
  query, explicitly `del`s it + `gc.collect()`s, THEN loads the judge —
  never both resident at once, per D-049's stated hardware constraint).
  New `--with-judge` CLI flag. Re-checks the SAME (claim, source_id)
  pairs Qwen already judged, independently, by resetting `verified` to
  `None` and re-running `verify_citations()` with the judge in place of
  Qwen — reuses `citation_verifier.py` completely unchanged. Reports
  and logs (to `docs/eval_log.md`, a new dated section distinct from
  the single-judge entries) both models' independent accuracy AND the
  agreement rate between them — the disagreement signal is the actual
  point of D-049, not just a second accuracy number.
- `test_phase10_judge_comparison.py` — sandbox validation with two
  independent stub models, including the specific case that matters
  most: Qwen says "supported", judge says "not supported" — confirms
  the disagreement is correctly counted and surfaced, not silently
  averaged away.
**Files touched:** `tests/eval/judge_model.py` (new), `tests/eval/
citation_accuracy_eval.py`, `docs/eval_log.md`, `test_phase10_
judge_comparison.py` (new).
**Verification:** 212/212 across the full 14-file regression suite.
**Still not done, same as everything else in this thread:** no real
run. Requires downloading the actual Llama-3.1-8B-Instruct GGUF (not
done here — no network access to Hugging Face from this sandbox) and
running on real hardware. Folds into the same real-hardware batch
already on hold per Entry 030/031 — this adds one more command to that
list, not a new separate ask.

### D-051 — First real D-049/D-050 confirmation: dual-judge run completed; fixed a real reporting gap it exposed
**Phase:** 6/10, first real execution of `--with-judge` on real hardware
**Finding/Decision:** the user downloaded the real Llama-3.1-8B-Instruct
GGUF and ran `citation_accuracy_eval.py --with-judge` for real. It
completed successfully (11/12 queries; query 12 hit the same `n_ctx`
overflow from Entry 034, still unfixed -- see below). Result: **Qwen3-4B
self-judged accuracy 50.0%, Llama-3.1-8B judge accuracy 45.7%, agreement
rate 73.1% (19 agree / 7 disagree)** -- the first real dual-judge data
this project has ever produced, logged to `docs/eval_log.md`.

**A pattern in the per-query output looked like a bug and almost got
misdiagnosed as one.** Several queries showed `qwen(v=0,u=0)
judge(v=4,u=1)` -- Qwen apparently finding nothing, the judge finding
real verdicts on the SAME citations. Traced this to
`citation_verifier.verify_citations()`'s own documented fail-open
behavior: on a JSON parse failure, it returns citations UNCHANGED
(`verified` stays `None`, i.e. unchecked) rather than guessing. Qwen3-4B
failed to produce parseable structured output for the citation-
entailment task on roughly 5 of 12 queries; the judge, given the exact
same citations, succeeded. `agree=0 disagree=0` on those queries was
CORRECT (an unresolved verdict on either side is excluded from the
comparison, by design), not a bug.

**This IS real, valuable Phase 6 data, not just an explanation for
confusing output:** Qwen3-4B appears to have a meaningfully higher
parse-failure rate on this specific structured-JSON task than the 8B
judge -- a concrete, reproducible gap in the exact pairing this project
ships at runtime (`citation_verifier.py` uses Qwen3-4B, not a judge, in
production per D-006/D-032). This is precisely the kind of finding
D-001 named as justification for reconsidering fine-tuning.

**The real gap this exposed: `format_judge_comparison()` never printed
`unchecked` counts, only `verified`/`unverified`.** One query
(`"nuclear fusion"`) showed `qwen(v=7,u=2)` vs `judge(v=5,u=5)` -- 9
total vs 10 total, which LOOKED like a citation-count mismatch (a real
bug candidate) and could not be ruled out from the printed output alone.
Root cause turned out to be an unprinted unchecked citation on Qwen's
side that the judge then resolved -- not a bug, but the report couldn't
prove that on its own. Fixed: `JudgeComparisonResult` now carries
`qwen_unchecked`/`judge_unchecked`; both the console report and the
`docs/eval_log.md` entry now show these explicitly, plus a summary note
when Qwen's own unchecked count is nonzero, naming it as a reliability
signal rather than leaving it implicit.

**Still open, recurring, unaddressed:** query 12 (ISS) hit the exact
same `n_ctx` overflow class from Entry 034 (`8389` vs `9381` tokens
this time -- different number, same failure mode, same query). Two
independent real runs have now hit this. Still not fixed -- still
needs a deliberate truncation-strategy decision, not a mechanical patch,
per Entry 034's original flag. Recommend prioritizing this now that
it's recurred.
**Files touched:** `tests/eval/citation_accuracy_eval.py`
(`qwen_unchecked`/`judge_unchecked` fields, both construction sites in
`run_eval_with_judge()` and `main_with_judge()`, both formatting
functions), `test_phase10_judge_comparison.py` (+5 checks reproducing
the exact real-hardware scenario: Qwen's own call fails to parse, judge
succeeds on the same citations, unchecked counts now visible and
explained in the output rather than looking like a bug).
**Verification:** 232/232 across the full 15-file regression suite
(exact count re-verified, not estimated -- `test_phase10_judge_
comparison.py` is 19/19 with the 5 new checks included).

### D-052 — Manual analysis of D-051's real numbers found a concrete finding; automated it into the report
**Phase:** 6/10, follow-up to D-051's real dual-judge data
**Finding/Decision:** worked through D-051's real per-query numbers by
hand (reconstructed from the console output) to check whether the
73.1% aggregate agreement rate was evenly distributed or concentrated.
It's sharply concentrated: **of the queries where a real comparison was
possible, only 2 of them (`nuclear fusion`, `room-temp
superconductors`) account for ALL 7 disagreements** -- every other
comparable query (`CRISPR`, `2008 financial crisis`, `quantum
computing`) agreed 100%. On BOTH disagreeing queries, Qwen was the more
lenient side -- most strikingly on `room-temp superconductors`, where
Qwen rated all 4 of its own citations as supported while the judge
agreed with only 1 of the 4. That's a concrete, specific instance of
the self-preference/leniency risk D-049 named as the reason to use an
independent judge in the first place, not an abstract concern anymore.

Separately, `2008 financial crisis` showed perfect agreement that ALL 9
citations were UNSUPPORTED -- both models agreeing is a retrieval/
grounding quality signal, distinct from a judge-reliability signal, and
conflating the two would misread what's actually wrong.

**Automated this analysis into the harness** rather than leaving it as
a one-off manual exercise (which took real, error-prone hand
arithmetic to produce) -- `JudgeComparisonReport` gained three
properties: `disagreeing_queries` (sorted by disagreement count,
descending), `qwen_only_zero_queries` (Qwen-side parse failures the
judge resolved -- refines D-051's "~5/12" figure into an exact,
reproducible count), and `perfect_agreement_all_unsupported_queries`
(the retrieval-quality signal, kept distinct from disagreement).
`format_judge_comparison()` now prints a "Disagreement concentration"
section (only when disagreement exists -- silent otherwise, not noise
for the common case) that explicitly labels which side was more
lenient per query, since that label is the actionable part.
**Files touched:** `tests/eval/citation_accuracy_eval.py`,
`test_phase10_judge_comparison.py` (+4 checks, including confirming the
section is silent when there's no disagreement to report).
**Verification:** re-ran the new `format_judge_comparison()` against a
reconstruction of D-051's actual real-hardware numbers -- output
correctly identifies both disagreeing queries, correctly labels "Qwen
more lenient" on both, correctly separates the 4 Qwen-parse-failure
queries from the 2 true-zero-citation queries (a distinction D-051's
original "~5/12" estimate didn't have the data to make precisely).
236/236 across the full 15-file regression suite.
**Not yet re-confirmed against a NEW real run** -- this is validated
against a reconstruction of the existing real data, not a fresh
real-hardware execution of the new report code end-to-end. Recommend
the next `--with-judge` run confirm the new sections render correctly
in practice, not just against a hand-built test fixture.

### D-053 — Phase 8 macOS/Linux: GitHub Actions hosted runners, since no physical hardware exists
**Phase:** 8, unblocking macOS/Linux without owning either machine
**Finding/Decision:** user confirmed no Mac or Linux hardware is
available for the real-OS builds D-005/B-019 require. Rather than leave
Phase 8 indefinitely stuck on that, added
`.github/workflows/build-macos-linux.yml` using GitHub-hosted
`macos-latest`/`ubuntu-latest` runners -- these are REAL macOS and
REAL Linux machines (not emulation, not cross-compilation), free on a
public repo. This is the actual substitute for owning the hardware, not
a workaround that lowers the bar.

**Two tiers, deliberately separate:**
- **Tier 1** (runs on every push touching `src/`/`build/`, or manually):
  the real `build_macos.py`/`build_linux.py` PyInstaller build (which
  now also exercises B-019's platform guard for real, confirming it
  passes cleanly on the correct OS rather than just being unit-tested),
  plus two model-free smoke checks: `--help` (confirms the binary
  launches, no import/DLL/dylib crash) and a plain query expected to
  fail with a clean `ModelNotFoundError` (confirms the packaged
  binary's startup path works correctly on that real OS, distinguishing
  a packaging problem from "no model file" -- the same thing D-044's
  hook-firing confirmation established for Windows, achieved here
  without needing a multi-GB download on every run). Build artifacts
  are uploaded either way.
- **Tier 2** (manual `workflow_dispatch` input, off by default):
  downloads the real production model
  (`unsloth/Qwen3-4B-Instruct-2507-GGUF`, `Qwen3-4B-Instruct-2507-
  Q4_K_M.gguf`, ~2.5GB -- verified via web search against the actual
  Hugging Face repo, not guessed) and runs one real end-to-end query,
  the same bar D-044 met on Windows. Gated behind a manual trigger
  specifically because it adds real CI minutes and a large download to
  every run if left unconditional -- Tier 1 alone is cheap enough to run
  on every relevant push, Tier 2 is for deliberate confirmation runs.
**Files touched:** `.github/workflows/build-macos-linux.yml` (new).
**Verification:** YAML syntax validated. NOT yet actually run on GitHub
-- this workflow needs to execute on GitHub's infrastructure to be a
real confirmation, which this sandbox can't do (no ability to trigger
GitHub Actions runs from here). This is the honest state: the mechanism
is built and believed correct, but "believed correct" is not the same
bar as D-044's actual real-hardware confirmation, and shouldn't be
treated as such until it actually runs.
**Next step:** push this workflow file to GitHub (or merge it), then
either wait for Tier 1 to run automatically on the next relevant push,
or trigger it manually from the Actions tab with Tier 2 enabled for a
full confirmation run matching D-044's bar exactly.
### D-054 — Phase 8 macOS/Linux Tier 1 CONFIRMED on real hardware (via GitHub Actions); citation_verifier debug instrumentation added; B-020 confirmed fixed
**Phase:** 8 confirmation + 6 diagnostics
**Finding/Decision, Phase 8:** the `.github/workflows/build-macos-
linux.yml` workflow from D-053 ran for real -- pushed, triggered
automatically, both matrix jobs (`macos-latest`, `ubuntu-latest`)
completed with status **Success**, 3m59s total, 2 build artifacts
produced. This is genuine confirmation that `build_macos.py`/
`build_linux.py` (including B-019's platform guard, which had to pass
correctly on the real matching OS for the job to succeed at all) work
on real macOS and real Linux. **This is Tier 1 only** -- the build and
model-free smoke tests, not a full real-query grounded-answer
confirmation matching D-044's Windows bar. Tier 2 (manual
`workflow_dispatch` with `run_full_confirmation` checked) has not been
triggered yet. Two informational annotations (Node.js 20 deprecation
warnings on the underlying GitHub Actions themselves) appeared -- not a
Fathom issue, a GitHub Actions infra note, low priority, worth a future
`actions/checkout@v5`/`setup-python@v6` bump whenever convenient.

**Finding, Phase 6 -- citation_verifier reliability, escalated:** two
more real runs (plain + `--with-judge`) both showed a MORE severe
pattern than D-051 first found: 5 of 12 queries in the plain run had a
COMPLETE parse failure (100% of that query's citation batch left
unchecked), not just partial. Total unchecked count also rose (29 this
run vs 18 in the first plain run). A batch-size correlation looked
plausible at first glance (`nuclear fusion`'s 11-citation batch failed
completely) but a clean counterexample ruled out a simple explanation:
`CRISPR`'s 4-citation batch parsed perfectly while `2008 financial
crisis`, `quantum computing`, and `room-temp superconductors` -- also
4-citation batches -- failed completely. **Deliberately did NOT guess
a root cause or a fix from count data alone** -- added `debug_report`
threading to `citation_verifier.verify_citations()` so a parse failure
now surfaces the ACTUAL raw model response, batch size, and
`max_tokens` budget used, threaded through both `rag/graph.py` and
`tests/eval/citation_accuracy_eval.py`'s three call sites. This
doesn't fix the problem -- it makes the next real run capable of
actually diagnosing it (truncation vs. genuine malformation vs.
something else) instead of continuing to guess from aggregate counts.

**B-020 CONFIRMED FIXED on real hardware:** the corrected
`--self-consistency` query ran again -- `self-consistency: checked=True
flagged=[]`. No spurious `Note`/`Specifically`/citation-digit flags,
confirming the `raw_synthesized_answer` fix and the regex fixes both
hold on real output, not just the sandbox reconstruction from before.

**Honest revision to D-052's leniency-direction claim:** D-052,
working from ONE real run, found Qwen was the more lenient side on
both disagreeing queries and framed that as a signal worth watching.
THIS run's `--with-judge` execution shows the exact opposite: all 4
disagreements this time were "judge more lenient" (judge found MORE
citations supported than Qwen did). Two data points in opposite
directions do not support a stable one-directional bias claim --
correcting course rather than cherry-picking the run that fit the
earlier narrative. What DOES still replicate across both runs: Qwen's
own parse-failure/unchecked rate remains real and recurring (6
unchecked in this `--with-judge` run's Qwen phase, on top of the
plain run's 29). That's the part with two consistent data points, not
the leniency direction.

**Also fixed in passing:** a leftover duplicate line
(`judge_input = [...]` assigned twice, harmless but sloppy) from
D-051's edit, found while adding the debug threading.

**Files touched:** `src/verification/citation_verifier.py`
(`debug_report` param), `src/rag/graph.py` (threads it through),
`tests/eval/citation_accuracy_eval.py` (threads it through all three
call sites, dedup fix), `test_phase6_manual.py` (+6 checks, including
one reproducing a truncated-mid-array pattern).
**Verification:** 242/242 across the full 15-file regression suite.
**Not yet done:** Phase 8 Tier 2 (real model, real query, full D-044
parity) on macOS/Linux; the actual root-cause diagnosis of the
citation_verifier parse failures (now instrumented, but needs one more
real run to capture actual raw failure text); re-running the disagreement-
concentration analysis with a 3rd data point before drawing any
conclusion about leniency direction one way or the other.
### D-055 — Phase 9 started: model download source pinned, checksum verified
**Phase:** 9, prerequisite decision before any download code
**Finding/Decision:** before writing `model_downloader.py`, pinned an
exact, verified source rather than "whatever's current on the repo" --
`unsloth/Qwen3-4B-Instruct-2507-GGUF`,
`Qwen3-4B-Instruct-2507-Q4_K_M.gguf`. SHA256
(`3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`)
verified directly against Hugging Face's own file metadata via web
search, not guessed and not computed locally (no way to download the
real 2.5GB file in this sandbox to hash it directly). A checksum
mismatch at download time means either a corrupted transfer or the
upstream file changed out from under this pin -- either way, that's a
loud failure (`ChecksumMismatchError`), never a silent "close enough."
**Files touched:** `src/installer_support/model_downloader.py` (new).
**Verification:** N/A -- source-pinning decision, not code.

### D-056 — Phase 9: download-on-first-run architecture, one shared flow instead of three platform-specific downloaders
**Phase:** 9
**Finding/Decision:** considered building a separate frozen "installer
helper" executable per OS (a small PyInstaller-packaged binary each
installer would invoke to do the download) vs. having Fathom's own
binary handle it on first launch. Chose the latter: `src/main.py`
gained `_ensure_model_available()`, called right before `get_model()`,
which checks `resolve_model_path().exists()` (cheap, no hashing --
re-hashing a ~2.5GB file on every single launch would add real,
unacceptable startup latency for the common case) and downloads only
if missing. This means ONE download flow, covering both "installer
triggers first launch" and "someone just unzipped the build and ran it
manually" through the exact same code path, tested once
(`test_phase9_*.py`) instead of three times across platform-specific
scripts that would each need their own real-OS confirmation the way
`build_macos.py`/`build_linux.py` did in Phase 8.

Also added `--ensure-model`, a CLI flag that runs the download (or
confirms it's already present) and exits, no query required --
**caught and fixed a real bug in my own installer script while wiring
this in**: the Windows `.iss` draft originally used `fathom.exe
--help` to trigger the post-install download, which would never work,
since `--help` exits via argparse before `_ensure_model_available()`
ever runs. `--ensure-model` exists specifically so the installer
scripts have a correct, dedicated way to do this rather than a
workaround that silently wouldn't have worked.

**Built, per phases.md's Phase 9 file list:**
- `src/installer_support/model_downloader.py` -- streams the download
  to a `.part` temp file, verifies SHA256, only `os.replace()`s into
  the final path after the checksum passes (atomic on both POSIX and
  Windows -- an interrupted/corrupted download must never leave a bad
  file where `FathomModel` will later look for it). `verify_existing_
  model()` lets a re-run skip re-downloading ~2.5GB when a valid copy
  is already there, per `appflow.md` §7's update-flow spec.
- `src/installer_support/first_run_check.py` -- actually LOADS the
  model and runs one minimal generation, not just a file-exists check;
  a checksum match only proves the bytes are correct, not that
  `llama-cpp-python` can load them on this machine (wrong CPU
  instruction set, OOM, etc.) or that a loaded model produces output at
  all. Every failure mode returns a `FirstRunResult`, never raises --
  the caller here is an installer, not a developer wanting a traceback.
- `build/windows/installer.iss` -- Inno Setup script, per-user install
  (no admin needed, matching where the model cache already lives),
  optional post-install `--ensure-model` launch (unchecked by default
  -- a ~2.5GB download is a real cost the user should consciously opt
  into, not have sprung on them).
- `build/macos/postinstall.sh` -- written to `pkgbuild`'s documented
  postinstall contract, runs the download as the logged-in user (not
  root -- the model cache lives under the user's home directory, so a
  root-owned download would be unreadable by the user's own later
  `fathom` runs).
- `build/linux/install.sh` -- copies the `--onedir` build to
  `~/.local/share/fathom`, symlinks into `~/.local/bin`, triggers
  `--ensure-model`. **Actually functionally tested on this sandbox**
  (it's real Linux) with a stub binary -- confirmed the copy, the
  symlink, and the `--ensure-model` trigger all work correctly through
  the installed symlink, plus the missing-source-directory error path.
  This is real confirmation, not just a syntax check -- a stronger
  claim than what's possible for the Windows/macOS scripts, which
  genuinely need their native tools (`ISCC.exe`, `pkgbuild`) to verify.
**Files touched:** `src/main.py` (`_ensure_model_available()`,
`--ensure-model` flag), `src/installer_support/model_downloader.py`
(new), `src/installer_support/first_run_check.py` (new),
`build/windows/installer.iss` (new), `build/macos/postinstall.sh`
(new), `build/linux/install.sh` (new), `test_phase9_model_downloader.py`
(new, 19/19), `test_phase9_first_run_check.py` (new, 14/14),
`test_phase9_ensure_model_available.py` (new, 13/13, including full
CLI-level `--ensure-model` confirmation).
**Verification:** 288/288 across the full 18-file regression suite.
`install.sh` additionally functionally verified end-to-end on this
real Linux sandbox (copy/symlink/trigger all confirmed working, plus
the error path). `installer.iss` and `postinstall.sh` are written to
their platforms' documented, correct syntax but NOT yet compiled/run
on real Windows/macOS -- same "written correctly, not yet real-hardware
confirmed" status as every other platform-specific script in this
project until that happens.
**Not yet done:** real compilation of `installer.iss` via `ISCC.exe`
on Windows; real execution of `postinstall.sh` via an actual `.pkg`
install on macOS; a real end-to-end download (this sandbox has no
network access to Hugging Face, so `download_model()` is tested with
mocked `requests` only -- the real 2.5GB transfer, checksum match
against the real file, and `first_run_check.py`'s real model load have
never actually happened).
### D-057 — Phase 9 real confirmation: checksum verified correct, first_run_check confirmed, Windows installer compiles
**Phase:** 9, first real-hardware run
**Finding:** user ran the full Phase 9 sequence for real. Every piece
that could only be confirmed with a real download or real Windows
tooling is now confirmed:

- **The pinned SHA256 checksum (D-055) is CONFIRMED CORRECT against
  the real file.** A real ~2.38GB download completed
  (`100.0% (2381MB / 2381MB)` -- close to the ~2.5GB estimate, the
  estimate was always approximate) and `download_model()` printed
  "Fathom: model is ready." -- which only happens after
  `EXPECTED_SHA256` matches. Had the web-search-sourced hash been
  wrong, this would have raised `ChecksumMismatchError` and deleted
  the file instead. This was the single biggest unverified assumption
  in D-055; it's now real, not sourced-but-unconfirmed.
- **`first_run_check.py` confirmed for real:** `OK: Model loaded and
  generated output successfully: 'hi'` -- `load: 48.4s, generation:
  7.6s`. Real load time now on record (useful context for any future
  startup-latency work against `trd.md`'s NFRs).
- **A real query after the fresh download produced a correctly
  grounded, cited answer** (transistor invention year, 1947, multiple
  corroborating sources) -- confirms the download → first-run-check →
  normal-operation sequence works end-to-end, not just each piece in
  isolation.
- **`installer.iss` compiles with real `ISCC.exe`:** "Successful
  compile (48.578 sec)," produced `fathom-setup.exe`. Confirms the
  Inno Setup syntax was actually valid, not just written to look
  correct -- the `[Files]`, `[Icons]`, and `[Run]` sections all parsed
  without error against the real `dist/windows/fathom/` build output.
  **Not yet run** -- compiling is necessary but not sufficient; the
  installer itself hasn't been executed to confirm the actual install
  experience (file placement, Start Menu shortcut, the optional
  `--ensure-model` post-install launch).
- **GitHub Actions Tier 1 still green** after all of Phase 9's commits
  landed on top of it (`Success`, 4m29s, 2 artifacts) -- confirms
  nothing in this session's `citation_verifier.py`/`main.py` changes
  broke the macOS/Linux build. Same two cosmetic Node.js 20 deprecation
  warnings as before (GitHub Actions infra, not a Fathom issue).
**Files touched:** none -- this is a real-hardware confirmation entry,
not a code change.
**Still open:** actually RUNNING `fathom-setup.exe` to confirm the
install experience itself (not just that it compiles); Phase 8 Tier 2
(a real macOS/Linux query, still not manually triggered); real
`postinstall.sh` execution (still needs an actual Mac).
### D-058 — Phase 9 Windows track FULLY CLOSED on real hardware
**Phase:** 9, Windows track complete
**Finding:** the last three open items from D-057 all confirmed on
real hardware:
- `fathom-setup.exe` was actually RUN (not just compiled) — installed
  to a real path, ran end-to-end without error.
- The installed binary produces a correctly grounded, multi-source
  cited answer (boiling point query, 5 real sources) — proves the
  installed output works standalone, not just the dev build.
- `ls` on the install directory shows `fathom.exe`, `_internal/` (the
  bundled DLLs), AND `unins000.exe`/`unins000.dat` — Inno Setup's
  auto-generated uninstaller is present and correctly placed.
- Both Start Menu shortcuts from the `[Icons]` section confirmed
  present: `Fathom.lnk` and `Uninstall Fathom.lnk`, exactly matching
  what `installer.iss` declares -- nothing missing, nothing extra.

**Phase 9's Windows track now meets its own stated exit criteria in
full**: "clean install → working `fathom` command" -- installer
compiles, runs, places files correctly, creates both shortcuts, model
downloads and checksums correctly, and the installed binary produces
real grounded answers. Every piece of this was independently
uncertain at the start of this session (an unverified checksum, an
untested `.iss` syntax, an installer that had only ever been compiled,
never run) and is now confirmed, not assumed.
**Files touched:** none -- real-hardware confirmation entry.
**Still open, unchanged:** macOS (`postinstall.sh` needs a real Mac --
none available, per earlier discussion; D-053's GitHub Actions
workaround covers Phase 8's build/smoke-test tier but not a real `.pkg`
install experience) and Linux's `install.sh` (functionally tested on
this project's own sandbox already, per D-056, but not via a packaged
installer flow the way Windows now has). Phase 8 Tier 2 (a real
macOS/Linux query, not just build success) still not manually
triggered.
### D-059 — Phase 10 started: golden set + eval runner, scoped to what's NOT already covered
**Phase:** 10
**Finding/Decision:** `prd.md` §5 lists five success criteria. Before
building anything, checked which are already covered by existing
tooling to avoid duplicating work: "per-claim citation accuracy
tracked" is already `tests/eval/citation_accuracy_eval.py` (D-048) +
`docs/eval_log.md`'s real tracked history; "<6GB RAM / CPU-only" is an
architectural constraint (no GPU code anywhere), not something an eval
script measures -- a real memory profile during a real run is a
separate, manual check, not built here. That left TWO criteria with
zero existing coverage: refusal rate on off-domain queries (>=95%) and
zero silent hallucination (flagged low-confidence answers don't count
as failures). Built `tests/eval/golden_set.jsonl` (32 entries, 4
categories) and `tests/eval/golden_set_eval.py` scoped specifically to
measure those two.

**Categories, each mapping to a specific criterion:**
- `answerable` (10) — genuinely answerable research questions. Scored
  for the FALSE-POSITIVE direction of criterion #3: an over-eager
  domain_gate refusing a legitimate question is the opposite failure
  mode from under-refusing off-domain ones, and nothing previously
  tracked it.
- `off_domain` (10) — coding requests, creative writing, roleplay,
  translation, etc. Scored directly against `prd.md`'s stated >=95%
  threshold.
- `false_premise` (6) — reused the same class of query
  `answerability.py` was built for (D-045), scored as a distinct
  "catch rate" from domain refusal, since they're different subsystems
  (`domain_gate` vs `answerability`) and conflating them would hide
  which one is actually doing the work.
- `low_evidence` (6) — deliberately obscure/unanswerable-with-available-
  tools questions (private board meetings, unpublished data,
  real-time GPS of a specific truck). This is the direct probe for
  "zero silent hallucination."

**Explicit honesty constraint, stated in the module docstring and
enforced in the code, not just claimed:** this script CANNOT verify
factual correctness -- no component in this codebase can, including
`citation_verifier.py`'s own entailment check, which verifies a claim
against a CITED source, not against ground truth. What it CAN detect
is the proxy signal that would make silent hallucination POSSIBLE: a
confident answer with neither a citation tag nor a low-confidence
caveat. `low_evidence_review_candidates` names these explicitly as
"NOT a confirmed hallucination, needs manual check" in both the
console report and the log entry -- never overstated as a hallucination
detector.

Runs through `main.run_query()` (the REAL front door: `domain_gate` →
`router` → path), not a forced-agentic shortcut like
`citation_accuracy_eval.py` uses -- that distinction matters here
specifically, since off-domain and false-premise detection both
depend on gates a forced-agentic run would bypass entirely.
**Files touched:** `tests/eval/golden_set.jsonl` (new, 32 entries),
`tests/eval/golden_set_eval.py` (new), `test_phase10_golden_set_
eval.py` (new, 16/16 -- validates the classification logic for all
four categories plus the error-handling and empty-report paths, using
the exact same stub-model pattern established for the rest of this
project's eval tooling).
**Verification:** 304/304 across the full 19-file regression suite.
**Not yet done:** no real run -- this sandbox has no network access to
the retrieval tools or the real model, same standing gap as every
other eval tool in this project before its first real-hardware
execution. 32 entries is a starting set, not `trd.md` §7's full 50-100
-- expandable once real-run data shows which categories need more
coverage.
### D-060 — Integrated the eval-time judge (Llama-3.1-8B) into golden_set_eval.py's hallucination-risk check
**Phase:** 10
**Finding/Decision:** the "zero silent hallucination" heuristic in
`golden_set_eval.py` (D-059) was a pure presence check -- flags a
`low_evidence` answer as a review candidate if it has neither a
citation tag nor a low-confidence caveat. At the user's request,
extended this with a genuine second opinion from the same eval-time
judge model D-049/D-050 built (Llama-3.1-8B, `tests/eval/
judge_model.py`) -- NOT to replace the heuristic, but to give an
actual independent reading of the answer's content and epistemic
posture, which a regex fundamentally cannot do.

**Same honesty discipline as everywhere else in this eval tooling,
stated explicitly and enforced in the output, not just claimed:** the
judge has no more access to ground truth than the heuristic does.
What it adds is that it actually READS the answer and assesses
whether it presents unsupported claims with unwarranted confidence --
a qualitative judgment, not a fact-check. `format_hallucination_
verdicts()` and the `eval_log.md` entry both state explicitly "NOT
confirmed hallucinations" and "second model's opinion, not ground
truth" -- this is a stronger second look, never upgraded to a
detector.

**Added:** `judge_low_evidence_candidates()` (takes the already-
flagged candidates, asks the judge model to assess each one's
epistemic posture), `HallucinationRiskVerdict`, `format_
hallucination_verdicts()`, `append_hallucination_verdicts_to_log()`,
and `main_with_judge()` (new `--with-judge` flag on `golden_set_eval.py`
-- sequential loading, same pattern and same <6GB reasoning as
`citation_accuracy_eval.py`'s `main_with_judge()`: Qwen runs the full
golden set first, gets explicitly freed via `del` + `gc.collect()`,
THEN the judge loads to review only the flagged candidates, never both
resident at once).

**A real, useful finding surfaced while testing this, not a bug in the
new code:** `core/guardrail.py`'s `output_rail` already blocks a
confidently-stated, zero-citation answer whenever real chunks were
retrieved (`require_citations=True` in that case) -- replacing it with
the generic safety-fallback message before it could ever reach this
heuristic. Discovered because an early test draft tried to script
exactly that scenario through the real pipeline and got the generic
fallback message back instead. This is CORRECT, reassuring production
behavior, not a gap -- it means the actual hallucination-risk surface
in the fast path is narrower than "no citations at all" would suggest;
a more subtle real risk (a citation tag present but only weakly
supporting the claim) is what `citation_verifier.py`'s entailment
check exists to catch on the agentic path. Logged here rather than
silently worked around, since it's a genuine piece of information
about how the guardrails actually interact.
**Files touched:** `tests/eval/golden_set_eval.py`,
`test_phase10_golden_set_eval.py` (+10 checks; also fixed two
pre-existing test bugs found in the same pass -- `patch("rag.graph.
retrieve", ...)` alone doesn't cover `main.py`'s own directly-imported
`retrieve` reference, needed for fast-path-routed test queries, same
class of fixture issue hit several times earlier this session).
**Verification:** 314/314 across the full 19-file regression suite.
**Not yet done:** no real run of `--with-judge` on `golden_set_eval.py`
specifically -- same standing gap as every eval tool before its first
real-hardware execution, though `citation_accuracy_eval.py --with-judge`
(the sibling tool built on the same `JudgeModel`) has already been
confirmed working for real (D-051).
### D-061 — Third real run: false-premise catch rate 50%, n_ctx overflow recurred a 3rd time, real evidence sometimes still produces zero citations
**Phase:** 6/10, real-hardware run
**Finding:** user ran the full sequence (plain golden set, `--with-judge` golden set, plain citation eval, `--with-judge` citation eval). Network was down (DNS resolution failures) for roughly the first 5 minutes of the run -- not a Fathom bug; the pipeline degraded gracefully throughout (never crashed, always produced some response) and recovered automatically once connectivity returned.

**Real findings, independent of the network issue:**
1. **Golden set false-premise catch rate: 50.0%.** 3 of 6 false-premise
   queries were NOT correctly refused. This is the single most
   actionable result from this run -- it bears directly on "zero
   silent hallucination" (an unrecognized false premise, confidently
   answered, IS a hallucination by definition). Off-domain refusal
   (100%, exceeds the 95% `prd.md` threshold) and the answerable
   false-positive rate (0%) were both clean.
2. **Real evidence sometimes still produces zero citations.** Query 6
   (CRISPR) retrieved 20 real chunks on the FIRST attempt -- no
   network issue -- and still ended `answerable=False`,
   `0 verified/0 unverified/0 unchecked`. This is a cleaner
   demonstration of the Entry 034/035 mystery than any prior run: it
   can no longer be explained away as "no chunks were ever retrieved."
   Important scoping note: this ran through
   `citation_accuracy_eval.py`'s forced-agentic `run_agentic()` call,
   which deliberately bypasses `output_rail` (D-048) -- a real
   end-user query through `main.run_query()` would have caught a
   zero-citation answer and shown the safe fallback instead. This
   finding is about synthesis's own citation-instruction adherence,
   not necessarily something reaching real users.
3. **The `n_ctx` overflow recurred a THIRD time**, same query (ISS),
   different token count (8724 this time vs. 9381 and 8389
   previously). Three independent real runs, same failure class. No
   longer arguable as a fluke -- this is the clearest case yet for
   prioritizing the truncation-strategy fix flagged as far back as
   Entry 034 and never addressed.
4. **Qwen-vs-judge leniency direction remains genuinely mixed** (2
   "Qwen more lenient," 2 "judge more lenient" this run) -- continues
   to support D-054's correction of D-052's earlier one-directional
   framing.
**Files touched:** none yet -- this is a findings-only entry; no fix
has been chosen or implemented for any of the above.
**Verification:** N/A -- real-hardware data, not a code change.
**Still open, now with more evidence than before:** the false-premise
50% catch rate and the "real evidence, zero citations" pattern both
need further investigation before a fix is designed -- neither has an
obvious root cause yet from the data alone. The `n_ctx` overflow does
have enough repeated evidence now to justify prioritizing a fix.
### D-062 — Root-caused and fixed 2 of 3 D-061 findings; 3rd confirmed as correct safety behavior, not a bug
**Phase:** 6/10, closing D-061's findings for Windows (macOS/Linux held per user request, no hardware available)
**Finding/Decision:** debugged all three D-061 findings by reading code, not guessing from symptoms.

**Fix 1 — `n_ctx` overflow (3 independent real crashes, same failure class).**
Root cause confirmed by code inspection: `citation_verifier.py`
already truncates chunk content to 300 chars/claim, but
`rag/synthesis.py`'s `_format_sources()` embedded FULL, UNTRUNCATED
chunk content with no bound at all. With `top_k=8` real chunks (news
articles, web pages -- routinely several thousand characters each),
the synthesis prompt could exceed `DEFAULT_N_CTX=8192` outright,
crashing `generate()` before it could even attempt a response. Fixed:
added `_MAX_CHUNK_CHARS=2000` truncation in `_format_sources()`, with
the budget math shown in the constant's own comment (n_ctx minus
`DEEP_MODE_MAX_TOKENS`, minus system prompt/query/conversation-context
margin, divided across `top_k` chunks, with real headroom left for
tokenizer-estimate imprecision). Confirmed structurally against the
real ISS-query crash pattern (top_k=8 chunks accumulated across 3
retries, several of them long real web/news content).

**Fix 2 — golden set under-counting the false-premise catch rate.**
Root cause confirmed by code inspection, not assumption:
`golden_set_eval.py`'s `_classify_result()` only recognized TWO of the
FOUR distinct ways a query gets safely handled without an ungrounded
answer reaching the user (`domain_gate` refusal, `answerability`
refusal). It was missing:
  - `output_rail`'s generic fallback -- reachable when an AMBIGUOUS
    (low-confidence) answerability verdict fails open to synthesis per
    D-045's design, and synthesis then produces an uncited answer;
    `output_rail` correctly intercepts it. This exact chain (ambiguous
    answerability -> synthesis -> uncited answer -> output_rail
    fallback) is precisely what happened to the Eiffel Tower query
    back in status.md Entry 033/034 -- a SAFE outcome that was being
    scored as a false-premise-catch FAILURE.
  - `rag/synthesis.generate()`'s own hardcoded zero-chunk fallback ("I
    wasn't able to find any sources...") -- an HONEST "no evidence"
    response, also being under-counted.
Fixed: `_classify_result()` now recognizes all four cases distinctly
(`"domain"`, `"answerability"`, `"output_rail"`, `"zero_evidence"`).

**A real, corrected discovery made WHILE fixing #2, not assumed going
in:** `main.run_query()`'s `output_rail` call runs UNCONDITIONALLY
after BOTH the fast and agentic branches (confirmed by reading the
actual code, not assumed) -- meaning D-060's claim that `output_rail`
only "narrows" the fast path's hallucination-risk surface was
UNDERSTATED. For any query routed through `main.run_query()` (which is
what `golden_set_eval.py` uses), an uncited answer with real chunks
present is structurally UNREACHABLE, not just unlikely -- `output_rail`
eliminates that specific risk surface entirely for this entry point.
`low_evidence_review_candidates` is therefore, correctly, dead code
against `golden_set_eval.py`'s real pipeline specifically; kept as a
defensive property and now tested at the unit level (a manually
constructed `GoldenSetResult`) rather than forced through an
integration test that cannot actually reach it. D-060's text left
uncorrected in place; this entry supersedes its specific claim.

**Finding 3 — CRISPR query, real evidence, zero citations: NOT a bug.**
Root cause: `sufficiency` correctly identified, across all 3 retry
attempts, that the 20 real chunks retrieved per attempt (news
articles, GitHub repos, arXiv papers) were topically adjacent to
"CRISPR" but not substantively DEFINITIONAL -- none of Fathom's five
retrieval tools (web/news/arxiv/curated/github) are suited to "what is
X" foundational questions; they skew toward news, research, and code.
`sufficiency` and `answerability` correctly refused to fabricate a
definition from ill-fitting sources rather than hallucinate one. This
is the safety mechanism working AS DESIGNED, not a defect. A genuine
fix would be a FEATURE decision (e.g. adding a Wikipedia-style
encyclopedic retrieval tool) -- explicitly not implemented here without
discussing it first; flagged as a real, identified gap for a future
decision, not silently patched.
**Files touched:** `src/rag/synthesis.py` (`_MAX_CHUNK_CHARS`,
`_format_sources()`), `tests/eval/golden_set_eval.py`
(`_classify_result()`, `_OUTPUT_RAIL_FALLBACK_PREFIX`,
`_ZERO_EVIDENCE_PREFIX`), `test_phase4_manual.py` (+5 checks for the
truncation fix, including an 8-chunk realistic-worst-case
reconstruction of the actual crash pattern), `test_phase10_golden_set_
eval.py` (+3 checks reproducing the exact real-hardware Eiffel-Tower-
class scenario, and corrected Test 4 to unit-test the now-provably-
unreachable-via-real-pipeline scenario directly rather than force an
impossible integration test).
**Verification:** 325/325 across the full 19-file regression suite.
**Scope, per explicit user instruction:** Windows only. macOS and
Linux held -- no hardware available; will revisit once a device exists
for either. None of these three fixes are Windows-specific in their
code (they're pure Python, platform-agnostic), so they apply equally
once macOS/Linux testing resumes -- "Windows only" describes what's
been CONFIRMED, not a platform-conditional code path.
**Not yet done:** none of these three fixes have been run on real
hardware yet -- sandbox-verified against reconstructions of the actual
real-hardware failure patterns, same standing gap as everything else
in this project before its first real-hardware confirmation.

---

### D-063 — Fixed real findings from Entry 046's `--with-judge` re-run: citation_verifier's boolean-array parse gap (B-021), github_search self-throttle

**Context:** the real-hardware re-run confirmed D-062's `n_ctx`
truncation fix held (ISS query completed cleanly, no crash, first time
in four runs). Two NEW real findings came out of the same run, read
from the actual raw output rather than inferred:

1. Two queries (`inflation rate`, `room-temp superconductors`) hit
   `citation_verifier`'s fail-open path with `TypeError: 'bool' object
   is not subscriptable`. Traced to actual code
   (`verify_citations()`'s `item["index"]` access) against the actual
   raw response (`[false, false, false, true]`) -- the model answered
   the entailment question correctly, just as a flat boolean array
   instead of the requested `[{"index": N, "supported": bool}, ...]`
   object array. This was previously indistinguishable from a genuine
   parse failure and silently discarded 10 real verdicts across the
   run (5 citations each), inflating the "unchecked" count without any
   actual ambiguity in what the model said.
2. `github_search` failed with a real 403 rate-limit error
   (`solid-state battery` query) -- same failure class B-012 already
   fixed for arXiv (rapid successive calls under the agentic path's
   retry loop, no self-throttle), just never applied to this tool.

**Fix 1 (B-021):** `citation_verifier.verify_citations()` now checks
whether the parsed JSON array is entirely booleans before attempting
the object-shaped parse; if so, maps verdicts positionally
(`{i: bool(v) for i, v in enumerate(parsed)}`) instead of falling
through to fail-open. The object-shaped path is unchanged and still
tried first for anything that isn't a pure boolean array, so this is
additive, not a replacement. Explicitly logged as an ASSUMPTION, not a
guarantee: this trusts that the model preserved claim order and
dropped none -- reasonable given `_format_claims()` presents claims in
a fixed numbered order and the model is asked to answer "in the same
order given," but not provable from the array alone the way an
explicit `index` field would be. If this assumption ever proves wrong
in practice (e.g. a future run shows a boolean array shorter than
`to_check`), the existing `verdicts.get(check_idx)` lookup already
degrades safely -- missing entries stay `None` (unchecked), not
silently wrong.

**Fix 2:** `github_search.py` gets an identical self-throttle to
`arxiv_feed.py`'s (`_throttle()`, module-level `_last_call_time`),
tuned to GitHub's documented 10 req/min unauthenticated limit (one
call per 6s, per D-031). Explicitly scoped: this addresses the
*rapid-successive-calls* rate limit (the one that actually fired this
run), not GitHub's separate hourly quota (60/hr unauthenticated) --
no in-process throttle can prevent that one without an API key, which
would conflict with this project's no-API-key-required design (D-031).
Real-hardware confirmation of whether the 403 stops recurring is still
owed, same as every other fix in this project before its first
real-hardware run.

**Also logged:** D-062's `n_ctx` truncation fix is now CONFIRMED on
real hardware -- the ISS query, the specific query that crashed three
times running (Entries 034/035/044), completed cleanly this run with
no overflow. Closing that open item for real, not just code-complete.

**Files touched:** `src/verification/citation_verifier.py`,
`src/tools/github_search.py`, `test_phase6_manual.py` (+5 checks:
flat boolean array accepted, whitespace-formatted variant, empty-array
edge case, and a no-regression check that the original object shape
still works), `test_phase6_sources.py` (+4 checks for the throttle,
using a mocked clock so the test suite doesn't actually burn 6 real
seconds per run).
**Decided by:** Claude (session work), reviewed against real
Entry-046 terminal output rather than assumed from the pattern alone.
**Verification:** 273/273 across the full 16 sandbox-runnable test
files (Phase 9's model-download tests remain untestable here per the
same standing `llama-cpp-python`/network sandbox gap as every prior
session -- unrelated to this change).
**Not yet done:** neither fix has run on real hardware yet -- same
standing gap as everything else in this project before its first
real-hardware confirmation. The next `citation_accuracy_eval.py
--with-judge` run should show fewer/zero `unchecked` counts on queries
that previously hit this exact parse shape, and the next run touching
`github_search` should show whether the 403 stops recurring.
`golden_set_eval.py` (plain + `--with-judge`) still hasn't been
re-run since the D-062 classifier fix -- that's a separate, still-open
item, not closed by this entry.

---
**Return to `/context.md` for next steps.**

### D-064 — v1 explicitly scoped to Windows; macOS/Linux formally deferred, not dropped

**Context:** per `phases.md`, Phase 8/9's stated exit criteria are
"all three OSes." Windows is fully closed (D-044/D-057/D-058); macOS
is genuinely hardware-blocked (no Mac available, unchanged since
Phase 8 started); Linux is functionally tested directly (D-056) but
not yet via a packaged installer flow the way Windows now has.

**Decision:** per explicit user direction, v1 ships Windows-only.
This is a real, logged scope reduction from `phases.md`'s original
Phase 8/9 exit criteria, not a silent one — `phases.md`'s Phase 8/9
sections are left as-is (they still describe the v1 vision correctly),
and this entry plus `readme.md`'s own "Windows only for this release"
line are the record of the actual shipped scope. macOS and Linux are
DEFERRED, meaning: the code is not platform-specific (D-033's guard
exists precisely so the same Python runs on any OS once tested there),
Linux's `install.sh` already works when run directly, and macOS's
`postinstall.sh` is written and believed correct per spec but
unconfirmed. None of this is being thrown away — it's a documented
follow-up release (v1.1, informally), not a v2 feature.

**What this does NOT change:** Phase 10's exit criteria (real eval
numbers, `readme.md` finalized, v1.0 tag) still apply in full — scoping
platform down doesn't relax the evaluation/documentation bar. See
status.md Entry 047 for the specific items still open before tagging.

**Files touched:** `docs/status.md` (Entry 047), `docs/readme.md`
(finalized, explicit "Windows only for this release" line added).
**Not yet done:** the actual v1.0 tag — waiting on Entry 047's
still-open confirmation items, not on this scope decision itself.

---

### D-065 — False-premise catch rate shown to have real run-to-run variance (83.3% vs 50.0%, same code); v1.0 tag held pending a fix or a documented range

**Context:** two consecutive real `golden_set_eval.py` runs, ~53
minutes apart, no code changes between them: false-premise catch rate
went 83.3% → 50.0%. Traced against the actual per-query transcript
(not assumed): golden-set queries 22/23/24 (JWST-2019,
Wikipedia-2015, Australia-1975) are refused before retrieval in both
runs — stable. Queries 21 (Eiffel Tower), 25 (Python discontinued),
26 (Nintendo consoles) reach full generation in both runs; whether
they get caught depends on the POST-generation answerability re-check,
which flipped from 2/3 caught to 0/3 caught between the two runs.

**Root cause:** `llm_backend.py` defaults generation temperature to
0.2, not 0 — only `domain_gate.py`'s pre-check is deliberately
deterministic (`temperature=0.0`, with a comment explaining why:
"this is a classification, not..."). The post-generation answerability
re-check inherits the 0.2 default and is genuinely sampling different
outputs run to run on these three borderline-worded false premises.
This is real model stochasticity, not a scoring bug in
`golden_set_eval.py` itself.

**What this means for the numbers already in `readme.md` /
`decisions.md` D-064:** the 83.3% figure I wrote into `readme.md`
after Entry 047 was a single sample of a metric that just demonstrated
real variance, presented as if stable. That was premature — flagged
here rather than left uncorrected.

**Decision:** do NOT tag v1.0 on a single golden-set run's
false-premise number. Two options, not yet chosen between:
1. Run `golden_set_eval.py` N times (5+) and report a range/median for
   false-premise catch rate in `readme.md`, honestly reflecting the
   variance rather than hiding it behind one point estimate.
2. Set `temperature=0.0` for the post-generation answerability
   re-check specifically (mirroring domain_gate's existing reasoning),
   trading a small amount of the re-check's expressiveness for
   determinism on exactly the kind of borderline case this metric is
   supposed to measure — then confirm with a repeat run that the
   number stabilizes.
Option 2 is likely the better fix (it's the same reasoning
domain_gate already applies, just not yet extended to this second
classification step) but changes real generation behavior and should
be a deliberate call, not bundled silently into a docs fix.

**Not yet decided:** which of the two options to take. **Not yet
done:** either fix, and the repeat-run confirmation either would need.
**readme.md updated in the meantime** to show the real range (50.0%–
83.3%) rather than a single cherry-picked number, and to note the tag
is held pending this.

**Also confirmed this run (positive):** D-063's citation_verifier fix
is working — `unchecked` citations dropped 12 → 3 on the
`citation_accuracy_eval.py --with-judge` re-run (not yet zero; a
residual unparseable-shape case likely remains, lower priority than
D-065). `github_search`'s 403 did not recur in this run, consistent
with (not proof of) the throttle fix. Answerable false-positive
refusal rate held at 0.0% across both new golden-set runs — genuinely
stable so far, unlike the false-premise number.

**CORRECTION (logged same session, before any fix was applied on the
strength of the wrong claim):** the "Root cause" paragraph above is
WRONG. I asserted `classify_answerability()`'s post-retrieval re-check
runs at `temperature=0.2` without reading the actual function first.
Checked directly against `src/verification/answerability.py`:

```python
raw = model.chat(
    ...,
    max_tokens=80,
    temperature=0.0,  # deterministic classification, same rationale
    # as domain_gate.classify_domain -- do not raise without logging
    # why in decisions.md.
)
```

Both the pre-check and the post-retrieval re-check are already
deterministic. That path is not the source of the variance.

**Actual root cause, traced through `golden_set_eval.py`'s own
`_classify_result()`:** a query counts as "caught" via THREE distinct
paths, not one — `"answerability"` (the deterministic check above),
`"output_rail"` (an ambiguous-confidence answerability verdict lets
synthesis proceed per D-045's fail-open design, and `output_rail`
catches it afterward if synthesis produces an uncited answer), and
`"zero_evidence"`. `rag/synthesis.py`'s `generate()` defaults to
`temperature=0.3` — genuinely non-deterministic — so the SAME
retrieved evidence can synthesize into a cited vs. uncited answer on
different runs, changing whether `output_rail` catches it. Layered on
top: queries 21/25/26 also go through live retrieval
(`web_search`/`news_search`), which can itself return different
results ~53 minutes apart for time-sensitive queries — a second real
source of run-to-run difference in what evidence even reaches
synthesis. Both are genuine, neither is `classify_answerability`'s
temperature.

**Why this matters:** Option 2 as originally written ("set
`temperature=0.0` on the post-generation answerability re-check")
would have been a no-op — that call was already deterministic — and
implementing it would have given false confidence that the variance
was fixed when the actual sources (synthesis temperature +
live-retrieval variance) were untouched. Caught and corrected before
any code change was made on the strength of the wrong claim.

**Revised options, replacing the original two:**
1. (Unchanged) Run `golden_set_eval.py` N times and report a range —
   still valid regardless of root cause.
2. Lower `synthesis.generate()`'s default temperature for this
   specific call path, OR make `_classify_result()`/the eval harness
   re-run only the affected borderline queries multiple times to
   distinguish "genuinely ambiguous" from "flaky." Unlike the original
   Option 2, this one is unverified as a real fix — it would need to
   be tried and re-measured, not assumed to work.
3. NEW: cache/pin retrieval results within a single eval run (or
   across a short repeat-run window) so that citation/answerability
   variance can be isolated from retrieval variance — right now the
   two are confounded and it's not possible to tell how much each one
   contributes.
**Not yet decided. Not yet done.** This entry supersedes its own
earlier "Root cause"/"Decision" paragraphs above — those are left in
place per this project's own convention (never delete history), but
should not be treated as current.

---

### D-066 (fixes B-022) — Fast path had no retry on empty retrieval; confirmed as the dominant driver of D-065's variance, not model sampling

**Context:** user ran `golden_set_eval.py` twice back-to-back (~50 min
apart, run 1 finishing right before run 2 started) specifically to
separate retrieval variance from generation variance, per this
session's ask. Result: **run 1 shows `"Generating answer from 0
sources"` on queries 10, 25, and 28 — run 2 shows normal 5-8 sources on
all three.** This is a completely mechanical, unambiguous signal (zero
retrieved chunks), not a subtle sampling difference.

**Root cause, confirmed against actual code
(`src/main.py` line ~272-274, fast path):**
```python
report("Searching sources")
retrieved = retrieve(query, debug_report=debug_report)
chunks = rerank(retrieved, top_k=top_k, requires_recency=...)
```
Exactly one `retrieve()` call, no retry, no sufficiency check — unlike
the agentic path (`rag/graph.py`), which has a sufficiency-check loop
with up to 3 attempts (D-016 era work). `rag/retriever_hybrid.py`'s
`retrieve()` fans out across 5 independent tools, each wrapped in its
own try/except (D-033) so one tool failing doesn't fail the call — but
if ALL 5 come back empty at once (a shared transient blip: DNS hiccup,
momentary network interruption, etc.), there's nothing to catch that
at a higher level. It falls straight through to `synthesis.generate()`'s
hardcoded `zero_evidence` branch, producing an honest-but-wrong refusal
for queries that are genuinely answerable.

**This explains both halves of D-065's swing, not just one:**
- Query 25 (Python discontinued, false_premise) hit 0 chunks in run 1
  → refused, but for the WRONG reason (empty retrieval, not premise
  detection) — it happened to land on the "caught" side of the
  scoreboard by accident, inflating that run's catch rate.
- Queries 10 and 28 (answerable/low_evidence) also hit 0 chunks in run
  1 → wrongly refused, which is exactly why answerable false-positive
  refusal rate spiked to 20% that same run.
- Run 2, all three retrieved normally → catch rate and false-positive
  rate both returned to their prior values.

**This supersedes D-065's "revised options" list** — synthesis
temperature and live-retrieval content drift (both flagged as
co-suspects in D-065's correction) are not ruled out as smaller,
secondary contributors, but this is confirmed as the dominant,
first-order cause via two clean, mechanically-unambiguous data points.

**Fix:** `src/main.py`'s fast path now retries `retrieve()` exactly
once if the first call returns zero chunks, before falling through to
generation. Bounded (single retry, not a loop) — a transient blip gets
one more chance; a genuinely unfindable topic still correctly reaches
the honest `zero_evidence` refusal after 2 attempts, same as before.
Deliberately NOT matching the agentic path's full 3-attempt
sufficiency-check loop — that loop also re-plans sub-queries via an
LLM call, which is exactly the cost the fast path exists to avoid
(D-027); a bare retry of the same query is the right scope for this
path.

**Files touched:** `src/main.py`, new `test_phase10_fast_path_retry.py`
(12 checks: normal case unaffected, retry recovers from a transient
empty result, retry is bounded to exactly one attempt when both calls
fail, `debug_report` gets the retry notice only when a retry actually
happens).
**Verification:** 12/12 in the new test file; 285/285 across the full
17 sandbox-runnable test files (up from 273/16 — this session added
the new file).
**Not yet done:** real-hardware confirmation. The next `golden_set_
eval.py` run(s) should show `"Generating answer from 0 sources"`
becoming rare-to-absent (a genuine double-failure is possible but
should be much less common than a single transient one), and both
false-premise catch rate and answerable false-positive refusal rate
should show less swing between runs. If they still swing after this
fix, that's real evidence for D-065's secondary suspects (synthesis
temperature, retrieval content drift) actually mattering — worth
re-running the same back-to-back-runs test to check.
**Also worth doing, not done here:** the SAME zero-chunk-with-no-retry
gap could in principle affect the agentic path's very first retrieval
call too (before its own sufficiency loop kicks in) — not investigated
this session, flagged for a follow-up look rather than assumed fine.

---

### D-067 — D-066 CONFIRMED on real hardware (retrieval now stable); false-premise catch rate settles at a real, reproducible 50% — a genuine classifier limitation, not noise, and NOT changed without a deliberate tradeoff call

**Context:** user ran `golden_set_eval.py` twice back-to-back again,
post-D-066 fix. Result: **both runs show identical numbers** — 8
sources on every fast-path query (no `"0 sources"` at all, first time
this has happened across every run logged this session), 0.0%
answerable false-positive refusal rate (both runs), 50.0% false-premise
catch rate (both runs, exactly matching, not a range anymore).

**What this confirms:** D-066's fix works. The retrieval-flakiness
bug that was causing wrongful refusals on genuinely answerable queries
is gone — two clean, identical, back-to-back runs is real evidence,
not luck.

**What this reveals, now that the noise is gone:** false-premise catch
rate isn't flaky — it's a real, reproducible **50%**, and the earlier
83.3% readings were themselves the anomaly (likely produced by the
retrieval flakiness D-066 just fixed, in a way that happened to help
this specific metric by accident on those runs). Traced to
`answerability.py`'s evidence-based system prompt, quoted exactly:
> "Flag it as unanswerable ONLY if the premise itself is false or
> contradicted by the evidence -- NOT merely because the evidence is
> thin or incomplete (that's a sufficiency/retrieval concern, not this
> check's job)."

For queries like "Why did the Eiffel Tower collapse in 1990?", generic
web/news evidence about the Eiffel Tower essentially never contains an
explicit sentence denying a collapse that never happened — there's
nothing for 8 solid chunks to "contradict" the premise with, so the
classifier correctly follows its own instructions and doesn't flag it.
**This is deliberate, sensible-looking design, not a bug** — the
comment exists specifically to prevent the classifier from flagging
merely-thin evidence as a false premise, which would directly
reintroduce the exact answerable-false-positive problem D-066 just
fixed. No prior `decisions.md` entry documents this specific tradeoff
being chosen, though — it was written straight into the code as an
inline comment.

**Why this is NOT being changed in this entry:** loosening the
contradiction requirement (e.g. treating "evidence covers this entity
in depth but never mentions the claimed event" as a soft signal) is a
real, testable idea — but it trades directly against the metric D-066
just fixed. Making that change without a proper before/after
comparison on BOTH metrics would risk exactly the kind of "fixed one
number, broke the other, didn't notice" mistake this project has
already caught itself making more than once this session. Not doing
that again on a change with a known, direct tradeoff.

**Not yet decided:** whether to attempt a more targeted classifier
change (e.g. an "absence of expected corroboration for a significant,
checkable event" signal, worded carefully to stay conservative), or to
accept 50% as a real, documented limitation and expand the golden
set's false_premise category instead so the number rests on more than
3 swing queries. Either is legitimate; this entry exists to make the
tradeoff explicit before either is chosen, not to choose one.
**readme.md not yet updated** — the existing 50%-83.3% range is now
known to be wrong in a specific way (50% is the real stable number,
83.3% was the anomaly), but updating it should wait until the above is
decided, since the fix chosen would change the number again.

---

### D-068 — Expanded false_premise golden-set coverage 6 → 12 and split it into two subtypes (`pre_check_reliable` / `needs_evidence`), with per-subtype reporting

**Context:** the practical path chosen for D-067's open question:
improve the measurement before touching the model, since a blended
50% was resting on only 3 swing queries deciding the whole number, and
because "should this classifier change be made" needs to be judged
against real per-mechanism numbers, not one number averaging two
different catch mechanisms together.

**What was added — retroactive tagging (no query text changed):** the
existing 6 `false_premise` entries were tagged based on ACTUALLY
OBSERVED real-transcript behavior this session, not guessed: "Why did
the JWST shut down permanently in 2019?" / Wikipedia-2015 /
Australia-1975 consistently got refused BEFORE retrieval (the
query-only pre-check, which relies on the model's own knowledge, not
retrieved evidence) → tagged `pre_check_reliable`. Eiffel Tower-1990 /
Python-discontinued-2020 / Nintendo-2018 consistently reached full
retrieval and depended on the evidence-contradiction check (D-067's
subject) → tagged `needs_evidence`.

**What was added — 6 new entries**, 3 per subtype, doubling each
bucket to n=6: 3 more `pre_check_reliable` (well-known, heavily-
documented myths: faked Moon landing, Y2K catastrophe, "10% of the
brain") that should generalize the mechanism already shown reliable;
3 more `needs_evidence` (specific false claimed events about real,
still-operating companies, structurally identical to the original 3:
Amazon/Google/Netflix). `tests/eval/golden_set.jsonl` now has 38
entries total, 12 of them `false_premise`.

**Harness changes (`tests/eval/golden_set_eval.py`):**
`GoldenSetResult` gained an optional `subtype` field (defaults to
`None` — fully backward compatible, every other category is untagged
and stays untagged). `GoldenSetReport` gained `by_subtype()` and
`false_premise_catch_rate_by_subtype()`. `format_report()` and
`append_to_log()` both print a per-subtype breakdown line whenever any
tagged entries exist, and print nothing extra when they don't (old
golden sets / other categories unaffected).

**This is a measurement change only — nothing about model behavior,
prompts, or the classifier changed in this entry.** The blended
`false_premise_catch_rate` metric is computed exactly as before; this
only adds visibility into what's driving it.

**Files touched:** `tests/eval/golden_set.jsonl`,
`tests/eval/golden_set_eval.py`, `test_phase10_golden_set_eval.py`
(+9 checks: subtype rate computation, blended-rate non-interference,
unknown-subtype handling, untagged-entry isolation, report formatting
with and without subtypes present).
**Verification:** 41/41 in the golden-set-eval test file; 314/314
across the full 17 sandbox-runnable test files.
**Not yet done:** a real-hardware run against the expanded set. The
next `golden_set_eval.py` run will show the new subset breakdown lines
and give a genuinely more informative number than the old blended
50%/83.3% history — that result is the actual input D-067's classifier-
change decision should be made from, not the 3-query number that's
been driving it so far.

---
**Return to `/context.md` for next steps.**
