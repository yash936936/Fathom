import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/unit|manual/<file>.py -> repo root
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "tests" / "eval"))

from golden_set_eval import load_golden_set, run_golden_set, VALID_CATEGORIES  # noqa: E402
import watchlist_eval  # noqa: E402

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModel:
    def __init__(self, scripted_replies):
        self._queue = list(scripted_replies)

    def chat(self, messages, max_tokens=200, temperature=0.0, stop=None, on_token=None):
        if not self._queue:
            raise AssertionError("StubModel ran out of scripted replies")
        return self._queue.pop(0)


# --- Test 1: watchlist.jsonl loads via the SAME loader/validation as
# the full golden set -- no separate parsing logic to drift out of
# sync. ---
_WATCHLIST_PATH = _REPO_ROOT / "tests" / "eval" / "watchlist.jsonl"
entries = load_golden_set(_WATCHLIST_PATH)
check("watchlist.jsonl loads without error via load_golden_set", len(entries) > 0)
check("watchlist has exactly 6 curated entries (D-093 cycle)", len(entries) == 6)
check(
    "every watchlist entry uses a valid category (same rule as the full set)",
    all(e["category"] in VALID_CATEGORIES for e in entries),
)

# --- Test 2 (D-093): the 2 queries this watchlist cycle exists to
# re-check are actually present -- if someone edits watchlist.jsonl and
# accidentally drops one, this test catches it rather than silently
# testing a smaller set than intended. ---
_D093_TARGET_QUERIES = {
    "What are the most recent advances in room-temperature superconductors?",
    "What is the latest inflation rate in the United States?",
}
actual_queries = {e["query"] for e in entries}
check(
    "both D-093 target queries (the two answerable false-positive regressions) are present",
    _D093_TARGET_QUERIES.issubset(actual_queries),
)

# --- Test 3: watchlist_eval logs to its OWN file, never docs/eval_log.md
# -- the whole point is keeping ad-hoc runs out of the historical
# 50-entry trend log. Guard the actual path object, not just a string
# in a docstring. ---
check(
    "watchlist log path is separate from docs/eval_log.md",
    watchlist_eval._LOG_PATH != _REPO_ROOT / "docs" / "eval_log.md",
)
check(
    "watchlist log path lives under tests/eval/, not docs/",
    watchlist_eval._LOG_PATH.parent == _REPO_ROOT / "tests" / "eval",
)

# --- Test 4: append_to_watchlist_log actually writes a distinguishable
# entry (real file I/O against a temp-swapped path, not just checking
# the function exists). ---
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as tmpdir:
    fake_log = Path(tmpdir) / "watchlist_log.md"
    original_path = watchlist_eval._LOG_PATH
    watchlist_eval._LOG_PATH = fake_log
    try:
        report = run_golden_set(
            [{"query": "Write a Python function to reverse a list.", "category": "off_domain"}],
            StubModel(['{"in_domain": false, "confidence": 0.95, "reason": "coding request"}']),
        )
        watchlist_eval.append_to_watchlist_log(report)
        written = fake_log.read_text(encoding="utf-8")
        check("append_to_watchlist_log writes a real entry", "Watchlist eval" in written)
        check(
            "written entry is explicitly marked not-comparable to the full golden set",
            "not comparable to eval_log.md" in written,
        )
    finally:
        watchlist_eval._LOG_PATH = original_path

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
