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

---
**Return to `/context.md` for next steps.**
