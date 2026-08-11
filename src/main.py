"""
main.py — Fathom CLI entrypoint.

Two modes (see docs/decisions.md D-027):
  --mode deep  (default) -- full LLM-based domain check + adaptive
               routing (fast or agentic path). Thorough, slow.
  --mode quick -- heuristic domain check (no LLM call), always the fast
               path regardless of query complexity, tight max_tokens cap.
               Engineered to minimize cost as much as structurally
               possible -- NOT a guaranteed <30s ceiling (this hardware's
               measured ~1.7-2 tok/s makes a hard guarantee dishonest to
               promise; see D-027 for the full reasoning).

Output verbosity (--verbose / -v):
  default (quiet) -- a single-line spinner shows the current stage,
               fully cleared before anything else prints. Once done,
               ONLY the answer, its note (if any), and sources print --
               no stage log, no flags, no timing.
  --verbose    -- IDENTICAL spinner-based UI during processing (see
               decisions.md D-030 -- the old per-stage-log + live-token-
               streaming behavior was removed per explicit user request;
               it visually conflicted with the spinner writing to the
               same terminal anyway). The only difference: after the
               same clean answer + sources, an extra diagnostic footer
               (flags + elapsed time) prints for debugging.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Callable

import tools  # noqa: F401 -- registers built-in tools, see tools/__init__.py
from core.domain_gate import (
    REFUSAL_MESSAGE,
    DomainClassificationError,
    check_domain,
    quick_domain_check,
)
from core.guardrail import input_rail, output_rail
from core.llm_backend import ModelNotFoundError, get_model
from core.router import route
from core.state import new_state
from core.ui import Spinner, make_stage_reporter
from rag.reranker import rerank
from rag.retriever_hybrid import retrieve
from rag.synthesis import generate

QUICK_MODE_MAX_TOKENS = 120  # tight cap -- see module docstring on why
DEEP_MODE_MAX_TOKENS = 512


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fathom",
        description="Fathom -- a local, citation-grounded research CLI.",
    )
    parser.add_argument("query", nargs="?", help="A research question.")
    parser.add_argument(
        "--mode",
        choices=["quick", "deep"],
        default="deep",
        help="quick = fastest we can make it (heuristic domain check, "
        "fast path only, short answer) -- not a guaranteed time limit. "
        "deep = full accuracy (LLM domain check, adaptive routing). "
        "Default: deep.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="After the answer, also print flags and elapsed time for "
        "debugging. Processing UI itself is unchanged (same spinner).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Max tokens for the final answer. Default: 120 in quick "
        "mode, 512 in deep mode.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Max retrieved chunks to keep after reranking (default: 8).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw diagnostic detail (sub_queries per retrieval "
        "attempt, tool success/failure, citation verification counts) "
        "as plain lines to stderr, independent of --verbose's footer. "
        "For developers diagnosing retrieval/verification behavior.",
    )
    return parser


def run_query(
    query: str,
    model,
    *,
    mode: str,
    max_tokens: int,
    top_k: int,
    report: Callable[[str], None],
    stream_tokens: bool,
    debug_report: Callable[[str], None] | None = None,
) -> tuple[str, str, list[str], bool]:
    """Returns (answer_text, sources_block, flags, already_streamed).

    `already_streamed` is True only when the fast path's synthesis ran
    with live token streaming (verbose mode) -- the caller must not
    print `answer_text` again in that case, it's already on stdout.

    `report` is called with a short stage description at each step --
    the caller decides whether that becomes a spinner update or a
    printed line (see core/ui.py). `debug_report`, if given, surfaces
    raw diagnostic detail (sub_queries, tool success/failure, citation
    verification counts) independent of the spinner UI -- see
    decisions.md D-033, added after D-030's simplified --verbose
    accidentally removed visibility needed to diagnose B-007.
    """
    state = new_state(query)

    input_result = input_rail(query)
    if not input_result.passed:
        return (
            "This request was flagged by input safety checks and can't be processed.",
            "",
            input_result.flags,
            False,
        )

    report("Checking request")
    if mode == "quick":
        # No LLM call -- see decisions.md D-027. Heuristic, fails open.
        state["domain_ok"] = quick_domain_check(query)
        state["domain_confidence"] = None
    else:
        try:
            state = check_domain(state, model)
        except DomainClassificationError:
            state["domain_ok"] = True
            state.setdefault("guardrail_flags", []).append("domain_classifier_parse_failure")

    if not state["domain_ok"]:
        return (REFUSAL_MESSAGE, "", state.get("guardrail_flags", []), False)

    state = route(state)
    if mode == "quick":
        # Quick mode never goes agentic, regardless of what the
        # heuristic complexity classifier says -- the agentic path's
        # multiple chained LLM calls are exactly the cost quick mode
        # exists to avoid. See D-027.
        state["path"] = "simple"

    already_streamed = False

    if state["path"] == "complex":
        report("Planning multi-step research")
        from rag.graph import run_agentic

        final_state = run_agentic(query, model, top_k=top_k, report=report, debug_report=debug_report)
        answer = final_state.get("answer", "")
        chunks = final_state.get("retrieved_chunks", [])
    else:
        report("Searching sources")
        retrieved = retrieve(query, debug_report=debug_report)
        chunks = rerank(retrieved, top_k=top_k, requires_recency=state.get("requires_recency", False))

        report(f"Generating answer from {len(chunks)} sources")
        on_token = None
        if stream_tokens:
            print("", file=sys.stderr)  # blank line before streamed tokens start

            def on_token(token: str) -> None:  # noqa: F811
                print(token, end="", flush=True)

            already_streamed = True

        answer, _citations = generate(query, chunks, model, max_tokens=max_tokens, on_token=on_token)
        if stream_tokens:
            print("\n", file=sys.stderr)

    out_result = output_rail(answer, require_citations=bool(chunks))
    flags = state.get("guardrail_flags", []) + out_result.flags

    if not out_result.passed:
        return (
            "[The answer failed output safety/quality checks -- this "
            "usually means retrieved sources were insufficient. Try "
            "rephrasing.]",
            "",
            flags,
            False,
        )

    sources_block = ""
    if chunks:
        sources_block = "Sources:\n" + "\n".join(
            f"  [{c['source_id']}] {c['source']}" + (f" - {c['url']}" if c.get("url") else "")
            for c in chunks
        )

    return (answer, sources_block, flags, already_streamed)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.query:
        print('Fathom\nUsage: fathom "your research question" [--mode quick|deep] [--verbose]', file=sys.stderr)
        return 1

    max_tokens = args.max_tokens
    if max_tokens is None:
        max_tokens = QUICK_MODE_MAX_TOKENS if args.mode == "quick" else DEEP_MODE_MAX_TOKENS

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"Fathom: {exc}", file=sys.stderr)
        return 2

    start = time.monotonic()

    # Same clean single-line spinner UI in both quiet and verbose mode
    # now -- per user request, verbose no longer prints a stage-by-stage
    # log or streams tokens live (that combination visually conflicted
    # with the spinner writing to the same terminal anyway). The ONLY
    # difference --verbose makes now is an extra diagnostic footer
    # (flags + elapsed time) after the clean answer, nothing during.
    if args.debug:
        # --debug bypasses the spinner entirely -- plain diagnostic
        # lines and a threaded \r-repainting spinner would visually
        # collide on the same terminal (same conflict category D-030
        # already fixed for streaming vs spinner). See decisions.md
        # D-033.
        report = make_stage_reporter(verbose=True, spinner=None)

        def debug_report(msg: str) -> None:
            print(f"[debug] {msg}", file=sys.stderr)

        answer, sources_block, flags, _already_streamed = run_query(
            args.query,
            model,
            mode=args.mode,
            max_tokens=max_tokens,
            top_k=args.top_k,
            report=report,
            stream_tokens=False,
            debug_report=debug_report,
        )
        print(answer)
    else:
        with Spinner() as spinner:
            report = make_stage_reporter(verbose=False, spinner=spinner)
            answer, sources_block, flags, _already_streamed = run_query(
                args.query,
                model,
                mode=args.mode,
                max_tokens=max_tokens,
                top_k=args.top_k,
                report=report,
                stream_tokens=False,
            )
        # Spinner's __exit__ has already cleared the line by this point.
        print(answer)
    if sources_block:
        print(sources_block)

    if args.verbose:
        # The only thing --verbose still adds: a diagnostic footer after
        # the same clean output everyone else sees, not a different
        # process display.
        elapsed = time.monotonic() - start
        if flags:
            print(f"\n[flags: {', '.join(flags)}]", file=sys.stderr)
        print(f"[{elapsed:.1f}s, mode={args.mode}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
