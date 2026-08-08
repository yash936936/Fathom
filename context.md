# context.md — Agent Entry Point

> **This is the FIRST file to read at the start of any session.**
> Every other markdown file in `/docs` must end its task by redirecting back here.
> If you (the agent) ever land directly on another `/docs/*.md` file without having
> read this one first in the current session, stop and read this file before proceeding.

---

## 0. What this project is

**Fathom** — a small-scale, open-source, offline-first CLI research assistant.
CLI command: `fathom "your question"`.
- Base model: **Qwen3-4B-Instruct-2507** (GGUF, Q4_K_M, ~2.5GB), Apache 2.0, no fine-tuning.
- Retrieval: hybrid (BM25 + dense) + adaptive agentic RAG via LangGraph.
- Scope: **research queries only** — freshness/trend tracking, not coding, not general reasoning.
- Delivery: single downloadable installer per OS (Windows/macOS/Linux), model auto-downloads on install.
- Hard constraint: dev/runtime target is CPU-only, <6GB RAM footprint.

Full detail lives in `/docs/prd.md` (what/why) and `/docs/trd.md` (how/constraints).

---

## 1. File map — where everything lives

```
/context.md              ← you are here (ROOT ONLY — nowhere else)
/docs/
  prd.md                 ← product requirements: goals, users, scope, success criteria
  trd.md                 ← technical requirements: stack, models, constraints, NFRs
  architecture.md         ← full system structure: every file/folder + its job
  phases.md               ← build plan: phases, files touched per phase, exit criteria
  code_logic.md            ← core algorithm/pseudocode per module (routing, RAG loop, guardrails, hallucination checks)
  appflow.md               ← end-user flow: install → first run → query → answer
  workflow.md              ← how the agent should work: dev loop, doc-update rules, commit discipline
  decisions.md             ← append-only log of every design/code decision made, with rationale
  debug.md                 ← append-only log of every debug session and its fix
  status.md                 ← current phase, last action, next action — updated EVERY run
  readme.md                 ← public-facing project readme, evolves as phases complete
/src/                        ← actual code, structure defined in architecture.md
/build/                      ← installer scripts (Inno Setup, pkg, shell)
/models/                     ← NOT committed — runtime download target only
```

---

## 2. Routing rules (read this before touching any file)

| If you are about to... | Go to | Then log in |
|---|---|---|
| Understand product goals/scope | `docs/prd.md` | — |
| Understand tech stack/constraints | `docs/trd.md` | — |
| Understand file/module structure | `docs/architecture.md` | — |
| Know what to build next | `docs/phases.md` | `docs/status.md` |
| Understand an algorithm before coding it | `docs/code_logic.md` | — |
| Understand the user-facing flow | `docs/appflow.md` | — |
| Make ANY design/code decision | — | `docs/decisions.md` |
| Fix a bug / finish debugging | — | `docs/debug.md` |
| Finish ANY task, of any kind | — | `docs/status.md` |
| Update public docs after a phase completes | `docs/readme.md` | `docs/status.md` |

**Golden rule:** every completed task, no exceptions, ends with an update to
`docs/status.md`. Decisions go to `decisions.md` at the moment they're made
(not batched at the end). Debug sessions go to `debug.md` at the moment they're
resolved (not batched).

---

## 3. Standard session loop

1. Read `context.md` (this file).
2. Read `docs/status.md` to see current phase + last logged action.
3. Read `docs/phases.md` to confirm what the current phase requires.
4. Open only the specific `docs/*.md` files that phase references.
5. Do the work.
6. Log decisions as they happen → `docs/decisions.md`.
7. Log debug fixes as they happen → `docs/debug.md`.
8. On task completion → update `docs/status.md` (phase, what was done, what's next).
9. Return to this file's routing table if unsure what to do next. Never guess a
   file's purpose — this table is authoritative.

---

## 4. Non-negotiable constraints (repeat here so they're never missed)

- No fine-tuning in v1 (see `decisions.md` entry D-001 for rationale).
- CPU-only, <6GB RAM — every dependency choice must respect this (see `trd.md`).
- Domain scope enforced by classifier gate, never by system-prompt-only (see `architecture.md`).
- No gateway/microservice layer — CLI runs in-process (see `decisions.md` D-007).
- Every synthesis output must carry per-claim citations, verified before return (see `code_logic.md`).

**End of context.md — return here whenever unsure where to go next.**
