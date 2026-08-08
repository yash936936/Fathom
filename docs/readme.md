# Fathom

> Redirect: after reading, return to `/context.md` for routing.
> This file is copied/adapted to the repo root `README.md` at release points.
> Update it as phases complete (per `workflow.md` §3.5) — it should always
> reflect *actually working* capability, not planned capability.

## Status: Phase 0 — Planning & documentation complete
No functional code yet. See `docs/status.md` for live progress.

## What this is (planned)
A small, offline-first, open-source CLI research assistant. Ask a research
question, get an answer grounded in live retrieval with verifiable
citations — no GPU, no API key, single-installer setup.

- **Model:** Qwen3-4B-Instruct-2507 (Apache 2.0, GGUF, ~2.5GB)
- **Scope:** research questions only — not a coding or general chat tool
- **Runs on:** CPU only, <6GB RAM
- **Install:** single downloadable installer per OS; model downloads
  automatically during setup

## Why
Most research-assistant tools either require a paid API, send your queries
to a third party, or need a GPU. This is built to run entirely on modest
local hardware while still staying current on fast-moving topics via live
retrieval rather than stale fine-tuned knowledge.

## Installation
*(Not yet available — tracked in `docs/phases.md` Phase 9)*

## Usage
*(Not yet available — will show real examples once Phase 4/5 land)*

## Architecture
See `docs/architecture.md` for the full system design, `docs/prd.md` for
scope/goals, `docs/trd.md` for technical constraints.

## Contributing / development
See `docs/workflow.md` for the working process and `docs/phases.md` for the
current build plan.

## License
*(To be finalized — model is Apache 2.0; project license tracked as a
decision pending in `docs/decisions.md`.)*

---
**Return to `/context.md` for next steps.**
