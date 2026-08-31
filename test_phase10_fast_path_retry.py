"""test_phase10_fast_path_retry.py -- regression test for D-066/B-022:
the fast path used to call retrieve() exactly once with no retry, so a
transient all-tools-empty retrieval wrongly fell through to synthesis's
zero_evidence refusal. Confirmed on real hardware via two back-to-back
golden-set runs where the SAME queries got "0 sources" once and 5-8
sources ~50 minutes later (status.md Entry 049 / decisions.md D-066).

Uses mode="quick" throughout so the domain check and the pre-generation
answerability check are both skipped (both are LLM calls not relevant
to this retry logic) -- this isolates the retry behavior itself rather
than re-testing domain_gate/answerability, which already have their
own test files.
"""

import sys

sys.path.insert(0, "src")

from core.llm_backend import FathomModel  # noqa: E402
import main as main_module  # noqa: E402

passed = 0
failed = 0


def check(desc: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {desc}")
    else:
        failed += 1
        print(f"FAIL: {desc}")


class StubModel:
    """Minimal stand-in for FathomModel -- only .chat() is exercised,
    and only by synthesis.generate() in this test (quick mode skips
    every other model call in run_query)."""

    def chat(self, *args, **kwargs):
        return "A plain answer with no citations needed for this test."


def _make_chunk(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "source": "Test Source",
        "content": "Some retrieved content relevant to the query.",
        "url": None,
    }


# --- Test 1: first retrieve() call returns chunks -- no retry should
# happen, and retrieve() should be called exactly once. ---
call_log = []


def _retrieve_success(query, debug_report=None, **kwargs):
    call_log.append(query)
    return [_make_chunk("web:0")]


original_retrieve = main_module.retrieve
original_generate = main_module.generate
main_module.retrieve = _retrieve_success
main_module.generate = lambda *a, **kw: ("An answer. [web:0]", [])

call_log.clear()
answer, sources, flags, streamed = main_module.run_query(
    "What is the current state of nuclear fusion research?",
    StubModel(),
    mode="quick",
    max_tokens=256,
    top_k=8,
    report=lambda *a, **kw: None,
    stream_tokens=False,
)
check("normal case: retrieve() called exactly once when chunks are found", len(call_log) == 1)
check("normal case: answer is returned, not a refusal", answer == "An answer. [web:0]")
check("normal case: sources_block is non-empty (chunks were present)", "web:0" in sources)

# --- Test 2 (B-022/D-066): first retrieve() call returns EMPTY, second
# call (the retry) returns real chunks -- the retry should kick in and
# the final answer should use the retried chunks, not silently refuse. ---
call_count = {"n": 0}


def _retrieve_empty_then_success(query, debug_report=None, **kwargs):
    call_count["n"] += 1
    if call_count["n"] == 1:
        return []  # simulates the real-hardware "0 chunks" blip
    return [_make_chunk("news:0"), _make_chunk("arxiv:1")]


main_module.retrieve = _retrieve_empty_then_success
captured_chunks = {}


def _generate_capture(query, chunks, model, **kwargs):
    captured_chunks["chunks"] = chunks
    return ("Recovered answer. [news:0]", [])


main_module.generate = _generate_capture

call_count["n"] = 0
answer, sources, flags, streamed = main_module.run_query(
    "What are the most recent advances in room-temperature superconductors?",
    StubModel(),
    mode="quick",
    max_tokens=256,
    top_k=8,
    report=lambda *a, **kw: None,
    stream_tokens=False,
)
check("B-022: retrieve() is called exactly twice (initial + one retry)", call_count["n"] == 2)
check("B-022: the retried (non-empty) chunks are what synthesis actually used", len(captured_chunks["chunks"]) == 2)
check("B-022: final answer reflects successful recovery, not a refusal", answer == "Recovered answer. [news:0]")
check("B-022: sources_block reflects the retried chunks", "news:0" in sources and "arxiv:1" in sources)

# --- Test 3: BOTH retrieve() calls return empty -- should still fall
# through to the honest zero_evidence path (via generate()'s own
# hardcoded branch), not retry forever or crash. Exactly 2 calls, not
# 3+ -- confirms this is a single bounded retry, not a loop. ---
call_count["n"] = 0


def _retrieve_always_empty(query, debug_report=None, **kwargs):
    call_count["n"] += 1
    return []


main_module.retrieve = _retrieve_always_empty
main_module.generate = lambda *a, **kw: ("I don't have enough information to answer this.", [])

answer, sources, flags, streamed = main_module.run_query(
    "What is the latest inflation rate in the United States?",
    StubModel(),
    mode="quick",
    max_tokens=256,
    top_k=8,
    report=lambda *a, **kw: None,
    stream_tokens=False,
)
check("B-022: exactly 2 retrieve() calls when both are empty (bounded retry, not a loop)", call_count["n"] == 2)
check("B-022: still reaches generate()'s zero_evidence path honestly (no crash)", "enough information" in answer)
check("B-022: sources_block is empty when both retrieval attempts failed", sources == "")

# --- Test 4: debug_report is called with the retry notice when (and
# only when) the retry actually happens. ---
debug_messages = []


def _debug_report(msg):
    debug_messages.append(msg)


call_count["n"] = 0
main_module.retrieve = _retrieve_empty_then_success
main_module.generate = lambda *a, **kw: ("ok", [])
call_count["n"] = 0
debug_messages.clear()
main_module.run_query(
    "What are the main causes of the 2008 financial crisis?",
    StubModel(),
    mode="quick",
    max_tokens=256,
    top_k=8,
    report=lambda *a, **kw: None,
    stream_tokens=False,
    debug_report=_debug_report,
)
check(
    "B-022: debug_report receives the retry notice",
    any("retrying once" in m for m in debug_messages),
)

debug_messages.clear()
main_module.retrieve = _retrieve_success
call_log.clear()
main_module.run_query(
    "What year was the transistor invented?",
    StubModel(),
    mode="quick",
    max_tokens=256,
    top_k=8,
    report=lambda *a, **kw: None,
    stream_tokens=False,
    debug_report=_debug_report,
)
check(
    "B-022: debug_report does NOT get a retry notice when the first call already succeeded",
    not any("retrying once" in m for m in debug_messages),
)

main_module.retrieve = original_retrieve
main_module.generate = original_generate

print(f"\n{passed}/{passed + failed} checks passed")
if failed:
    sys.exit(1)
