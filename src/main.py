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
from core.llm_backend import ModelNotFoundError, get_model, resolve_model_path
from core.router import route
from core.state import new_state
from core.ui import Spinner, make_stage_reporter
from rag.reranker import rerank
from rag.retriever_hybrid import retrieve
from rag.synthesis import generate
from verification.answerability import check_answerability, refusal_message

QUICK_MODE_MAX_TOKENS = 120  # tight cap -- see module docstring on why
DEEP_MODE_MAX_TOKENS = 512


def _ensure_model_available() -> None:
    """Phase 9 (appflow.md §1, decisions.md D-055/D-056): if the
    production model isn't at resolve_model_path() yet, download it
    now, with a live progress line, before get_model() ever tries to
    load it.

    Deliberately does NOT re-verify an EXISTING file's checksum on
    every launch -- installer_support/model_downloader.py's
    download_model() already checksums right after downloading, and
    hashing a ~2.5GB file on every single app invocation (not just the
    first) would add real, unacceptable startup latency for the common
    case where the model is already correctly in place. A cheap
    existence check is enough to decide "already installed" for
    day-to-day launches; full verification stays a download-time (or
    explicit, on-demand) concern, not a per-launch one.

    This single insertion point covers both the installer-triggered
    first launch AND a user manually running `fathom` for the first
    time without ever having run a separate installer step (e.g. a
    developer running from source, or someone who just unzipped the
    --onedir build) -- appflow.md's install-time download sequence and
    "just run the binary" both funnel through the exact same code path,
    on purpose, so there's only one download flow to maintain and test.
    """
    if resolve_model_path().exists():
        return

    from installer_support.model_downloader import ChecksumMismatchError, DownloadError, download_model

    print(
        "Fathom: downloading the model (one-time, ~2.5GB)...",
        file=sys.stderr,
    )

    def _progress(downloaded: int, total: int) -> None:
        pct = (downloaded / total * 100) if total else 0.0
        mb_done = downloaded // (1024 * 1024)
        mb_total = total // (1024 * 1024)
        print(
            f"\r  {pct:5.1f}%  ({mb_done}MB / {mb_total}MB)",
            end="", file=sys.stderr, flush=True,
        )

    try:
        download_model(progress_callback=_progress)
    except (DownloadError, ChecksumMismatchError) as exc:
        print(file=sys.stderr)  # end the in-progress \r line cleanly
        raise RuntimeError(str(exc)) from exc
    print(file=sys.stderr)  # newline after the final progress line


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
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start an interactive multi-turn session (Phase 7). "
        "Follow-up questions can reference prior answers in the same "
        "session. Type 'exit' or 'quit' to leave, or Ctrl+C/Ctrl+D.",
    )
    parser.add_argument(
        "--self-consistency",
        action="store_true",
        help="Enable self_consistency.py on the agentic path (off by "
        "default as of D-046 -- adds a full extra synthesis call per "
        "query; see decisions.md D-045/D-046 for the unresolved "
        "real-hardware latency cost this is meant to help measure). "
        "No effect in --mode quick or on queries that route to the "
        "fast/simple path.",
    )
    parser.add_argument(
        "--ensure-model",
        action="store_true",
        help="Download the model if it isn't already present, then "
        "exit -- no query needed. Intended for installer scripts "
        "(build/windows/installer.iss, build/macos/postinstall.sh, "
        "build/linux/install.sh) to trigger the ~2.5GB download as an "
        "explicit install-time step, and for anyone who wants to "
        "pre-download without asking a question yet. Exits 0 if the "
        "model is already present or downloads successfully, 2 on "
        "failure -- same exit codes as a normal run's model-loading "
        "failure path.",
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
    conversation_context: str = "",
    enable_self_consistency: bool = False,
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

    `conversation_context`, if given (Phase 7, D-041), is prior Q&A
    history from --chat mode's ConversationBuffer. Threaded ONLY into
    synthesis (both paths) -- domain_gate, router, and retrieval all
    still see just `query` on its own, unchanged. See D-041 for why.

    `enable_self_consistency`, default False (D-046) -- see
    rag/graph.py's run_agentic() docstring. Only affects the agentic
    path; the fast path never runs self-consistency at all (it's not
    in code_logic.md §3's spec for that path).
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

        # enable_self_consistency defaults to False (D-045 §2 / D-046)
        # -- unresolved real-hardware cost. Now exposed via --self-
        # consistency for exactly the real-hardware timing runs D-045/
        # D-046 called for, rather than staying only settable from code.
        final_state = run_agentic(
            query, model, top_k=top_k, report=report, debug_report=debug_report,
            conversation_context=conversation_context,
            enable_self_consistency=enable_self_consistency,
        )
        answer = final_state.get("answer", "")
        chunks = final_state.get("retrieved_chunks", [])
    else:
        report("Searching sources")
        retrieved = retrieve(query, debug_report=debug_report)
        chunks = rerank(retrieved, top_k=top_k, requires_recency=state.get("requires_recency", False))

        if not chunks:
            # Per decisions.md D-066: real-hardware runs showed the
            # fast path had NO retry on a completely empty retrieval,
            # unlike the agentic path's sufficiency-check loop (up to
            # 3 attempts). A transient blip (all 5 tools momentarily
            # returning nothing at once) then fell straight through to
            # synthesis's hardcoded zero_evidence branch, wrongly
            # refusing answerable queries -- confirmed via two
            # back-to-back real golden-set runs where the SAME queries
            # got "0 sources" once and 5-8 sources ~50 minutes later.
            # One retry, same query, is enough to distinguish a real
            # blip from a genuinely unfindable topic, without adding
            # the full multi-attempt replanning cost of the agentic
            # path to every fast-path query.
            if debug_report:
                debug_report(
                    "fast path: initial retrieval returned 0 chunks, retrying once"
                )
            retrieved = retrieve(query, debug_report=debug_report)
            chunks = rerank(
                retrieved, top_k=top_k, requires_recency=state.get("requires_recency", False)
            )

        # Per code_logic.md §3 step 3 (Phase 6, D-045): a cheap
        # false-premise check before spending a synthesis call. Skipped
        # in quick mode -- quick mode's entire purpose (D-027) is
        # minimizing LLM calls, and this is exactly one more call that
        # mode is built to avoid; deep mode pays it since accuracy, not
        # latency, is deep mode's stated priority.
        if mode != "quick":
            report("Checking whether the question is answerable")
            a_verdict = check_answerability(query, model, chunks=chunks)
            if debug_report:
                debug_report(
                    f"answerability: answerable={a_verdict.answerable} "
                    f"ambiguous={a_verdict.ambiguous} reason={a_verdict.reason!r}"
                )
            if a_verdict.ambiguous:
                state.setdefault("guardrail_flags", []).append("answerability_ambiguous")
            elif not a_verdict.answerable:
                # Early return, same pattern as the domain-refusal branch
                # above: bypasses output_rail entirely rather than
                # risking its require_citations check rejecting a
                # citation-free refusal message and replacing it with
                # the generic failure text.
                state.setdefault("guardrail_flags", []).append(
                    f"answerability_failed:{a_verdict.reason}"
                )
                return (
                    refusal_message(a_verdict.reason),
                    "",
                    state.get("guardrail_flags", []),
                    False,
                )

        report(f"Generating answer from {len(chunks)} sources")
        on_token = None
        if stream_tokens:
            print("", file=sys.stderr)  # blank line before streamed tokens start

            def on_token(token: str) -> None:  # noqa: F811
                print(token, end="", flush=True)

            already_streamed = True

        answer, _citations = generate(
            query, chunks, model, max_tokens=max_tokens, on_token=on_token,
            conversation_context=conversation_context,
        )
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


def run_chat_loop(model, mode: str, max_tokens: int, top_k: int) -> int:
    """Interactive multi-turn session (Phase 7, D-041). Each turn runs
    through the same run_query() pipeline as a single-shot invocation --
    domain_gate/router/retrieval all see the raw follow-up question,
    unchanged; only synthesis additionally sees the conversation history
    via `conversation_context`. Uses the same clean spinner UI as
    default quiet mode for each turn.
    """
    from memory.conversation_buffer import ConversationBuffer

    buffer = ConversationBuffer()
    print("Fathom chat mode -- type 'exit' or 'quit' to leave (Ctrl+C/Ctrl+D also work).\n")

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            break

        context = buffer.format_context()
        with Spinner() as spinner:
            report = make_stage_reporter(verbose=False, spinner=spinner)
            answer, sources_block, _flags, _streamed = run_query(
                query,
                model,
                mode=mode,
                max_tokens=max_tokens,
                top_k=top_k,
                report=report,
                stream_tokens=False,
                conversation_context=context,
            )
        print(answer)
        if sources_block:
            print(sources_block)
        print()

        buffer.add_turn(query, answer)

    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.ensure_model:
        # Handled BEFORE the "no query" check below -- --ensure-model
        # is explicitly a no-query invocation, per its own help text.
        try:
            _ensure_model_available()
        except RuntimeError as exc:
            print(f"Fathom: {exc}", file=sys.stderr)
            return 2
        print("Fathom: model is ready.", file=sys.stderr)
        return 0

    if not args.chat and not args.query:
        print('Fathom\nUsage: fathom "your research question" [--mode quick|deep] [--verbose] [--chat]', file=sys.stderr)
        return 1

    max_tokens = args.max_tokens
    if max_tokens is None:
        max_tokens = QUICK_MODE_MAX_TOKENS if args.mode == "quick" else DEEP_MODE_MAX_TOKENS

    try:
        _ensure_model_available()
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"Fathom: {exc}", file=sys.stderr)
        return 2

    if args.chat:
        return run_chat_loop(model, args.mode, max_tokens, args.top_k)

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
            enable_self_consistency=args.self_consistency,
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
                enable_self_consistency=args.self_consistency,
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
