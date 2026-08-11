# architecture.md — Complete System Structure

> Redirect: after reading, return to `/context.md` for routing.
> This file is the single source of truth for file/folder layout. `phases.md`
> references these exact paths — keep them in sync if structure changes, and
> log the change in `decisions.md`.

## 1. Design principle
Single-process CLI application. No gateway, no microservices, no network
hops between internal components (see `decisions.md` D-007) — everything
below runs in one Python process on the user's machine. The only network
calls are outbound: retrieval tools and the one-time model download.

## 2. Full repository layout

```
fathom/
├── context.md                     # agent entry point (root only)
├── README.md                      # generated from docs/readme.md at release time
├── docs/                          # all planning/process docs — see context.md routing
│   ├── prd.md
│   ├── trd.md
│   ├── architecture.md            # this file
│   ├── phases.md
│   ├── code_logic.md
│   ├── appflow.md
│   ├── workflow.md
│   ├── decisions.md
│   ├── debug.md
│   ├── status.md
│   └── readme.md
│
├── src/
│   ├── main.py                    # CLI entrypoint (typer/click), arg parsing, dispatch
│   │
│   ├── core/
│   │   ├── router.py              # complexity classifier: fast-path vs agentic-path
│   │   ├── domain_gate.py         # research-domain classifier (guardrail entrypoint)
│   │   ├── guardrail.py           # NeMo Guardrails config + input/output rail hooks
│   │   ├── llm_backend.py         # llama-cpp-python wrapper around Qwen3-4B GGUF
│   │   ├── state.py               # ResearchState TypedDict — shared state object
│   │   └── ui.py                  # spinner / stage-reporter (D-027)
│   │
│   ├── rag/
│   │   ├── retriever_hybrid.py    # BM25 + dense retrieval, RRF fusion
│   │   ├── reranker.py            # cross-encoder rerank of fused results
│   │   ├── graph.py               # LangGraph definition: planner→retrieve→check→synth
│   │   ├── planner.py             # query decomposition node
│   │   ├── curator.py             # relevance/quality filter pass, pre-sufficiency
│   │   ├── sufficiency.py         # "enough evidence?" node + retry-loop control
│   │   └── synthesis.py           # answer generation with forced per-claim citation tags
│   │
│   ├── verification/
│   │   ├── citation_verifier.py   # per-claim (claim, source) entailment check
│   │   ├── answerability.py       # pre-retrieval false-premise / answerable check
│   │   └── self_consistency.py    # multi-sample variance check (agentic path only)
│   │
│   ├── tools/
│   │   ├── registry.py            # common tool-calling schema + dispatch
│   │   ├── web_search.py
│   │   ├── news_feed.py
│   │   ├── arxiv_feed.py
│   │   ├── github_search.py       # D-031 -- GitHub REST search, no API key
│   │   ├── reddit_search.py       # D-031 -- Reddit public .json search, no API key (fragile, unofficial)
│   │   └── vector_store.py        # curated local source DB (hybrid search backend)
│   │
│   ├── memory/
│   │   └── conversation_buffer.py # short-term only in v1; long-term is v2 extension point
│   │
│   └── installer_support/
│       ├── model_downloader.py    # first-run download, checksum, resume logic
│       └── first_run_check.py     # sanity-check model loads correctly post-install
│
├── build/
│   ├── build_windows.py           # PyInstaller build script (run on Windows)
│   ├── build_macos.py             # PyInstaller build script (run on macOS)
│   ├── build_linux.py             # PyInstaller build script (run on Linux)
│   ├── hooks/
│   │   └── hook-llama_cpp.py      # required PyInstaller hook for compiled lib
│   ├── windows/
│   │   └── installer.iss          # Inno Setup script, includes post-install download
│   ├── macos/
│   │   └── postinstall.sh         # .pkg postinstall script — model download
│   └── linux/
│       └── install.sh             # shell installer (curl | sh pattern)
│
├── tests/
│   ├── eval/
│   │   └── golden_set.jsonl       # offline eval queries + expected criteria
│   └── unit/                      # per-module tests, mirrors src/ structure
│
└── requirements.txt
```

## 3. Component descriptions (agent-facing)

| File/Module | Responsibility | Depends on |
|---|---|---|
| `main.py` | Parses CLI args, initializes app, dispatches query to `router.py` | all `core/` |
| `core/router.py` | Adaptive RAG routing: classifies query complexity, sends to fast path (single retrieval pass) or agentic path (`rag/graph.py`) | `core/domain_gate.py` |
| `core/domain_gate.py` | Classifies query as in-domain (research) or not; hard refusal on out-of-domain, before any retrieval spend | `core/llm_backend.py` (small/fast classifier call) |
| `core/guardrail.py` | Wraps NeMo Guardrails rails: input (injection/PII), output (safety, format) | `core/llm_backend.py` |
| `core/llm_backend.py` | Single point of contact with Qwen3-4B GGUF via llama-cpp-python; all generation calls go through here | model file at runtime cache path |
| `core/state.py` | Defines `ResearchState` — the typed object threaded through the LangGraph run | used by all `rag/` nodes |
| `core/ui.py` | Terminal progress display: single-line spinner (default) vs per-stage log (`--verbose`); see `decisions.md` D-027 | used by `main.py`, threaded into `rag/graph.py` via a `report` callback |
| `rag/retriever_hybrid.py` | BM25 + dense search, Reciprocal Rank Fusion | `tools/vector_store.py`, `tools/web_search.py` |
| `rag/reranker.py` | Cross-encoder reranking of fused hybrid results | — |
| `rag/planner.py` | Decomposes a research query into sub-questions + tool selection | `core/llm_backend.py` |
| `rag/curator.py` | Filters retrieved chunks for relevance/quality/recency before sufficiency check (pattern from company-research-agent, see `decisions.md` D-010) | `rag/reranker.py` output |
| `rag/sufficiency.py` | Judges if retrieved evidence answers the query; controls retry loop (capped, exhaustion surfaces as explicit caveat not silent fallback) | `core/llm_backend.py` |
| `rag/synthesis.py` | Generates the final answer, forcing per-claim source-ID tags | `core/llm_backend.py` |
| `rag/graph.py` | Wires the above into the LangGraph state machine (agentic path only) | all `rag/*` |
| `verification/answerability.py` | Pre-retrieval check for false-premise/unanswerable queries | `core/llm_backend.py` |
| `verification/citation_verifier.py` | Post-synthesis: verifies each (claim, cited source) pair via entailment check | retrieved chunks + synthesis output |
| `verification/self_consistency.py` | Samples synthesis multiple times (agentic path only), flags high-variance claims | `core/llm_backend.py` |
| `tools/*` | Individual tool implementations behind a shared schema in `registry.py` | external APIs |
| `memory/conversation_buffer.py` | Short-term, single-session context only in v1 | `core/state.py` |
| `installer_support/model_downloader.py` | Runs at install-time (or first-run fallback) to fetch the GGUF, verify checksum, support resume | build/ installer scripts call this |

## 4. Data flow (single query, high level)
```
CLI input → domain_gate → [refuse | continue]
          → router → [fast path | agentic path]
          → (fast: retrieve→rerank→synthesize)
          → (agentic: graph.py full loop)
          → answerability + citation_verifier
          → guardrail output rail
          → CLI output
```
Full node-level detail is in `code_logic.md`.

## 5. v2 extension points (documented, not built)
- `core/gateway.py` — only if multi-user/service mode is ever needed.
- `memory/long_term_store.py` — cross-session vector memory. Reference
  pattern (not the implementation) if built: garrytan/gbrain's contradiction-
  detection and citation-fixing concepts — rejected for v1 because its
  reference deployment needs Postgres/an embedder service/8GB+ RAM, which
  conflicts with `trd.md` §1. See `decisions.md` D-010.
- `core/multi_agent/` — only if single-agent RAG plateaus (see `decisions.md` D-003).
- `core/smart_router.py` — routing across multiple hosted models/fallback.
- `tools/browser_tool.py` — CDP-based browser automation (pattern:
  browser-use/browser-harness) for sources a search API can't reach.
  Deferred: adds a Chrome runtime dependency, too heavy for v1 footprint.
- `tools/social_trends.py` — optional plug-in tool (pattern:
  Panniantong/Agent-Reach) for free, cookie-based read access to Reddit/
  Twitter/YouTube — directly useful for the "daily trend" requirement, but
  kept optional since it shells out to several upstream CLIs and expands
  the dependency surface beyond `trd.md`'s minimal-footprint default.
- **Tool registry backend, pluggable:** `tools/registry.py`'s schema-driven
  design (already in v1) is compatible with swapping in a managed backend
  like ComposioHQ/composio later for broader tool coverage — not adopted
  as a v1 dependency because it requires a cloud API key/account, which
  conflicts with `trd.md`'s "no API key required for core operation"
  requirement. See `decisions.md` D-010.

---
**Return to `/context.md` for next steps.**
