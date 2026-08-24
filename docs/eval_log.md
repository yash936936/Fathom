# eval_log.md — tracked metric history

Appended to by `tests/eval/citation_accuracy_eval.py` (D-048). Each
entry is one real run of the per-claim citation accuracy metric
required by `trd.md` §7 / `phases.md`'s Phase 6 exit criteria, against
`tests/eval/phase6_citation_queries.jsonl`. Newest entries are appended
at the bottom, oldest first -- do not reorder or delete prior entries;
this file's value is the trend over time, not just the latest number.

Do not hand-edit an entry's numbers. If a run needs to be discarded
(bad model, broken environment), leave the entry in place and note why
in `status.md` instead of deleting history here.

**No real run has been logged yet** — every entry below `main()`
appends comes from an actual `python tests/eval/citation_accuracy_eval.py`
invocation against the real model and real retrieval tools on real
hardware. Sandbox mechanics were validated separately, with a stub
model, in `test_phase6_citation_eval_harness.py` — those are NOT real
numbers and are never written here.

(No `Return to /context.md` trailer on this file, unlike the rest of
`/docs/*.md` — `citation_accuracy_eval.py` appends new entries to the
end of this file automatically, so a trailer here would end up
sandwiched in the middle after the first real run instead of staying
at the true end.)

Two kinds of entries land here: single-judge accuracy runs (`python
tests/eval/citation_accuracy_eval.py`) and Qwen-vs-judge comparison
runs (`python tests/eval/citation_accuracy_eval.py --with-judge`,
D-049/D-050) — the comparison entries are headed "Qwen vs. Llama-3.1-8B
judge comparison" so the two are easy to tell apart at a glance.
