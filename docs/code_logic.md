# code_logic.md — Core Algorithm Logic

> Redirect: after reading, return to `/context.md` for routing.
> This file describes *how* each core node behaves — pseudocode/logic level,
> not implementation. Keep in sync with actual code; log any logic change in
> `decisions.md`, not here.

## 1. Domain gate (`core/domain_gate.py`)
```
input: raw user query
1. run fast classifier(query) -> {in_domain: bool, confidence: float}
2. if not in_domain and confidence > threshold:
     return REFUSAL (explicit reason: "research-only tool")
3. if confidence is low/ambiguous:
     pass through, flag for stricter output-side guardrail review
4. else: continue to router
```
Runs BEFORE any retrieval or generation cost is spent.

## 2. Router (`core/router.py`) — adaptive complexity routing
```
input: in-domain query
1. classify(query) -> {simple, complex}
   heuristics: query length, sub-question count estimate, keyword patterns
   (ambiguity/comparison/multi-entity language -> complex)
2. if simple: dispatch to FAST PATH
3. if complex: dispatch to AGENTIC PATH (rag/graph.py)
```

## 3. Fast path
```
1. retriever_hybrid.search(query)          # BM25 + dense + RRF
2. reranker.rerank(results, top_k)
3. answerability.check(query, results)     # quick pre-check
4. synthesis.generate(query, results)      # forced per-claim citations
5. guardrail.output_rail(answer)           # structural: tag present + ID resolves
                                            # (NOT citation_verifier.py -- that's a
                                            # HEAVY per-claim entailment call, deliberately
                                            # agentic-path-only per D-006/D-032; see D-045
                                            # for the correction of this earlier mislabel)
6. return answer
```

## 4. Agentic path (`rag/graph.py`, LangGraph)
```
state = ResearchState(original_query=query)

node PLANNER:
  sub_queries, tools_needed, requires_recency = llm.plan(query)
  state.sub_queries = sub_queries

node RETRIEVAL (parallel fan-out over sub_queries):
  for sq in sub_queries (parallel):
    results[sq] = retriever_hybrid.search(sq, tools_needed)
  state.retrieved_chunks = fuse(results)

node RERANK_FILTER:
  state.retrieved_chunks = reranker.rerank(state.retrieved_chunks, top_k)

node CURATOR:
  # Pattern extracted from company-research-agent (guy-hartstein) — a
  # dedicated relevance/quality filtering pass BEFORE sufficiency check,
  # separate from reranking. Rerank orders by relevance score; curation
  # additionally drops chunks that are off-topic, duplicate, or stale
  # relative to `requires_recency`, and tags each surviving chunk with a
  # short reason it was kept. Keeps SUFFICIENCY_CHECK from reasoning over
  # noisy/redundant evidence.
  state.retrieved_chunks = curator.filter(state.retrieved_chunks, state)

node SUFFICIENCY_CHECK:
  verdict, gap = llm.judge_sufficiency(state)
  if verdict == insufficient and state.retry_count < MAX_RETRIES:
     state.retry_count += 1
     refine sub_queries using `gap`
     -> back to RETRIEVAL
  elif verdict == insufficient and state.retry_count >= MAX_RETRIES:
     # Pattern from cobusgreyling/loop-engineering failure-mode catalog:
     # "loop stuck retrying, human never notified" is a named failure mode.
     # On cap exhaustion we do NOT silently proceed — we surface the gap
     # explicitly in the final answer as a caveat, so the retry ceiling is
     # visible to the user rather than papered over.
     -> SYNTHESIS (best-effort, with explicit "evidence incomplete" caveat)
  else:
     -> SYNTHESIS

node SYNTHESIS:
  state.answer, state.citations = llm.synthesize(state, force_citation_tags=True)

node VERIFICATION:
  answerability.check(state)               # false-premise catch, pre-generation ideally,
                                            # re-checked here for agentic multi-hop drift
  citation_verifier.check(state)           # per-claim entailment, not just structural
  if agentic_path:
     self_consistency.sample_and_check(state)  # only here — cost-gated, see D-006

node OUTPUT_GUARDRAIL:
  guardrail.output_rail(state.answer)

return state.answer
```
`MAX_RETRIES` = 2–3 (bounded — never an unbounded loop; see architecture.md
sufficiency-loop note).

## 5. Citation verifier (`verification/citation_verifier.py`)
```
input: answer with per-claim source tags, retrieved chunks
for each claim in answer:
  cited_source = resolve(claim.source_id, retrieved_chunks)
  if cited_source is None:
     flag(claim, "citation does not resolve")
  else:
     entailed = entailment_check(claim.text, cited_source.text)  # LLM or NLI model call
     if not entailed:
        flag(claim, "citation does not support claim")
if any flags:
  either strip/caveat flagged claims, or (if too many) fall back to REFUSAL
report: per-claim pass rate -> logged for eval tracking (trd.md §7)
```

## 6. Answerability check (`verification/answerability.py`)
```
input: query (+ retrieved context if available)
1. check for false premise / unanswerable framing
   (e.g., asks about an event with no valid basis, contradicts known timeline)
2. if false premise detected: return REFUSAL with explanation, skip synthesis
3. else: continue
```
Runs both pre-retrieval (cheap check on query alone) and post-retrieval
(re-checked against what was actually found) on the agentic path.

## 7. Self-consistency check (`verification/self_consistency.py`, agentic path only)
```
input: query, retrieved context
1. sample synthesis N times (N=2, the observable minimum -- see D-045
   for why NOT the 2-3 range originally sketched here) at a HIGHER
   temperature than default synthesis (0.7 vs 0.3 -- deliberately: a
   genuinely uncertain claim needs room to actually vary across samples
   for this check to detect anything; low-temperature resampling makes
   every sample nearly identical regardless of underlying uncertainty
   and defeats the point)
2. compare key factual claims (numbers, dates, named entities) across samples
3. if high variance on a claim: flag as low-confidence, caveat in final answer
   rather than silently presenting it as certain
```
Gated behind `enable_self_consistency` (default **False** as of D-045 §2 —
see decisions.md: each additional sample is a full extra synthesis call,
and this project's own measured per-call latency (D-022/D-029: ~140-3277s,
cause of variance still unresolved) makes an unconditional-on default an
unresolved cost, not a settled one. Turn on explicitly once real-hardware
timing data for this check specifically exists.)

## 8. Guardrail output rail (`core/guardrail.py`)
```
input: candidate answer
1. NeMo output rail: safety/toxicity/PII scrub
2. format check: citations present, refusal format correct if applicable
3. if fails: do not return raw model output — return safe fallback message
```

## 9. External logic references (extracted patterns, not dependencies)
See `decisions.md` D-010 for the full review. Summary of what was folded in:
- **Curator node** (§4, between rerank and sufficiency) — pattern from
  guy-hartstein/company-research-agent's `curator.py` relevance-filtering
  step.
- **Retry-cap-with-explicit-caveat** (§4 SUFFICIENCY_CHECK) — pattern from
  cobusgreyling/loop-engineering's failure-mode catalog (hard attempt caps,
  never silently retry forever, never silently proceed past a cap either).
- **Eval metric taxonomy** (see `trd.md` §7) — categories borrowed from
  google/agents-cli's evaluation framework (response quality, instruction-
  following, tool-use quality, safety, hallucination) rather than inventing
  our own from scratch.

---
**Return to `/context.md` for next steps.**
