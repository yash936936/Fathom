# tests/eval/ — scope split

Two different things live under this directory, on purpose, per
`phases.md`'s per-phase file ownership:

- **`citation_accuracy_eval.py` + `phase6_citation_queries.jsonl`**
  (this file's concern) — a SMALL, Phase-6-scoped harness that
  establishes and tracks the "per-claim citation accuracy" metric
  named in `trd.md` §7 and required by `phases.md`'s Phase 6 exit
  criteria. Not a general eval suite -- it exists to answer one
  specific question: of the citations Fathom's agentic path actually
  produces, what fraction hold up under `citation_verifier.py`'s
  entailment check? See `decisions.md` D-048.

- **`golden_set.jsonl`** (NOT built here — reserved for Phase 10) —
  the full 50-100 query offline eval set `trd.md` §7 and `phases.md`'s
  Phase 10 describe, covering the full metric taxonomy (final response
  quality, instruction-following, tool-use quality, safety,
  hallucination — not just citation accuracy). Do not build this file
  as part of Phase 6 work; it belongs to Phase 10 and phases.md's
  "work in order" rule means it shouldn't exist until Phase 8/9 close.

If you're looking for the full release-gating eval suite, it isn't
here yet — see `phases.md` Phase 10.
