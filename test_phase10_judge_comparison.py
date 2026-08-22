import sys
sys.path.insert(0, "src")
sys.path.insert(0, "tests/eval")

from unittest.mock import patch
from core.state import RetrievedChunk

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModel:
    def __init__(self, scripted_replies):
        self._queue = list(scripted_replies)
        self.call_log = []

    def chat(self, messages, max_tokens=200, temperature=0.0, stop=None, on_token=None):
        if not self._queue:
            raise AssertionError("StubModel ran out of scripted replies")
        reply = self._queue.pop(0)
        self.call_log.append(reply)
        return reply


FAKE_CHUNK = RetrievedChunk(
    source_id="web:0", content="The transistor was invented in 1947 by researchers at Bell Labs.",
    source="Test Source", url="http://example.com", date="2026-08-01", relevance_score=1.0,
)


def fake_retrieve(query, tool_names=None, max_results_per_tool=5, debug_report=None):
    return [FAKE_CHUNK]


PIPELINE_REPLIES = [
    '{"answerable": true, "confidence": 0.9, "reason": ""}',
    '{"sub_queries": ["q"], "requires_recency": false}',
    '{"sufficient": true, "gap": "", "search_query": ""}',
    "Invented in 1947 [web:0].",
    '{"answerable": true, "confidence": 0.9, "reason": ""}',
]

with patch("rag.graph.retrieve", side_effect=fake_retrieve):
    from citation_accuracy_eval import run_eval_with_judge, format_judge_comparison, JudgeComparisonReport

    # --- Test 1: Qwen and judge agree (both say supported) ---
    qwen_model = StubModel(PIPELINE_REPLIES + ['[{"index": 0, "supported": true}]'])
    judge_model = StubModel(['[{"index": 0, "supported": true}]'])
    comparison1 = run_eval_with_judge(["When was the transistor invented?"], qwen_model, judge_model)
    check("one query -> one result", len(comparison1.results) == 1)
    check("qwen verified count correct", comparison1.results[0].qwen_verified == 1)
    check("judge verified count correct", comparison1.results[0].judge_verified == 1)
    check("agreement counted", comparison1.results[0].agreements == 1)
    check("no disagreement", comparison1.results[0].disagreements == 0)
    check("agreement_rate is 100%", comparison1.agreement_rate == 1.0)
    check("qwen_accuracy and judge_accuracy both 100%", comparison1.qwen_accuracy == 1.0 and comparison1.judge_accuracy == 1.0)

    # --- Test 2: Qwen and judge DISAGREE -- this is the exact signal D-049 cares about ---
    qwen_model2 = StubModel(PIPELINE_REPLIES + ['[{"index": 0, "supported": true}]'])
    judge_model2 = StubModel(['[{"index": 0, "supported": false}]'])
    comparison2 = run_eval_with_judge(["transistor invented when"], qwen_model2, judge_model2)
    check("disagreement counted, not agreement", comparison2.results[0].disagreements == 1 and comparison2.results[0].agreements == 0)
    check("qwen accuracy (self-judged) still 100%", comparison2.qwen_accuracy == 1.0)
    check("judge accuracy (independent) is 0% -- exactly the divergence this exists to catch", comparison2.judge_accuracy == 0.0)
    check("agreement_rate reflects the disagreement (0%)", comparison2.agreement_rate == 0.0)

    # --- Test 3: judge model failure on one query doesn't kill the whole run ---
    class ExplodingJudge:
        def chat(self, *a, **k):
            raise RuntimeError("judge model crashed")

    qwen_model3 = StubModel(PIPELINE_REPLIES + ['[{"index": 0, "supported": true}]'])
    comparison3 = run_eval_with_judge(["transistor invention year"], qwen_model3, ExplodingJudge())
    check("judge crash recorded as a per-query error, not raised", comparison3.results[0].error is not None)

    # --- Test 4: format_judge_comparison doesn't crash on an empty report ---
    empty = JudgeComparisonReport()
    formatted_empty = format_judge_comparison(empty)
    check("format_judge_comparison handles empty report", "N/A" in formatted_empty)

    formatted = format_judge_comparison(comparison1)
    check("format_judge_comparison includes both models' accuracy labels", "Qwen3-4B" in formatted and "Llama-3.1-8B" in formatted)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
