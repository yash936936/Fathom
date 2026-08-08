# PRD — Product Requirements Document

> Redirect: after reading, return to `/context.md` for routing.

## 1. Problem statement
Researchers and knowledge workers need a lightweight, private, offline-capable
assistant that stays current with fast-moving topics (daily-updating trends,
news, papers) without depending on a paid API, without sending queries to a
third party, and without needing a GPU.

## 2. Product scope
**In scope:**
- Research question answering, grounded in live retrieval (web search, news,
  curated sources, arXiv-style feeds).
- Multi-hop research queries (decompose → retrieve → synthesize → cite).
- Citation-backed answers with verifiable sources.
- Fully local inference (no API key required for core operation).
- Single-command install, seamless model download, CLI usage.

**Explicitly out of scope (v1):**
- Coding assistance.
- General open-ended reasoning/chat unrelated to research.
- Multi-user/team features, accounts, cloud sync.
- Fine-tuning pipeline (superseded — see `decisions.md` D-001).

## 3. Target user
Individual researcher, analyst, student, or small team member who wants a
private, local, citation-grounded research tool and is comfortable with a CLI.

## 4. Core user stories
1. As a user, I download one installer, run it, and the tool is ready — no
   manual Python/model setup.
2. As a user, I ask a research question and get an answer with real,
   verifiable citations, not a confident guess.
3. As a user, if my question is outside the research domain (e.g. "write me
   code"), the tool declines clearly rather than attempting it.
4. As a user, if the tool cannot find reliable evidence, it tells me that
   directly instead of hallucinating an answer.
5. As a user, the tool works entirely offline for cached/previously-retrieved
   material, and gracefully explains when live retrieval is unavailable.

## 5. Success criteria
- Install-to-first-answer time under 5 minutes on a typical connection.
- Per-claim citation accuracy tracked and trending upward release over release
  (see `trd.md` §Evaluation).
- Refusal rate on off-domain queries ≥ 95% in eval set.
- Runs within the <6GB RAM / CPU-only constraint on the reference test machine.
- Zero silent hallucination in golden eval set (flagged low-confidence answers
  don't count as failures if they're correctly flagged).

## 6. Non-goals
- Beating frontier closed models on general benchmarks — not the goal.
- Supporting every OS/architecture on day one — Windows/macOS/Linux x86_64
  first, ARM/edge later.

## 7. Open questions (tracked, not blocking)
- Long-term memory (session persistence) — deferred to v2, see `phases.md`.
- Multi-agent orchestration — only if single-agent RAG demonstrably plateaus
  (see `decisions.md` D-003).

---
**Return to `/context.md` for next steps.**
