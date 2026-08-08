"""
main.py — Fathom CLI entrypoint.

Phase 4 scope (see docs/phases.md): full fast-path pipeline wired
end-to-end -- domain gate -> router -> retrieve -> rerank -> synthesize
-> output guardrail. The agentic path (router classifies a query as
"complex") is not yet implemented -- that's Phase 5's rag/graph.py.
Phase 4's own exit criteria only require the fast path to work.
"""

from __future__ import annotations

import argparse
import sys
import time

import tools  # noqa: F401 -- registers built-in tools, see tools/__init__.py
from core.domain_gate import DomainClassificationError, check_domain
from core.guardrail import input_rail, output_rail
from core.llm_backend import ModelNotFoundError, get_model
from core.router import route
from core.state import new_state
from rag.reranker import rerank
from rag.retriever_hybrid import retrieve
from rag.synthesis import generate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fathom",
        description="Fathom -- a local, citation-grounded research CLI.",
    )
    parser.add_argument("query", nargs="?", help="A research question.")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Max tokens for the final answer (default: 512).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Max retrieved chunks to keep after reranking (default: 8).",
    )
    return parser


def run_fast_path(query: str, model, max_tokens: int, top_k: int) -> tuple[str, list[str]]:
    """Returns (message_to_print, guardrail_flags). Implements
    code_logic.md §3's fast path exactly: retrieve -> rerank ->
    synthesize -> structural output check. Phase 6's per-claim citation
    verification and answerability pre-check are not wired in yet --
    output_rail()'s structural check (citation tags present) is the only
    grounding safeguard active at this phase.

    Prints progress to stderr at each stage -- per decisions.md D-021,
    a silent multi-minute wait is indistinguishable from a hang at
    current measured generation speeds. This does not fix the underlying
    latency; it makes the wait legible instead of ambiguous.
    """
    state = new_state(query)

    input_result = input_rail(query)
    if not input_result.passed:
        return (
            "This request was flagged by input safety checks and can't "
            "be processed.",
            input_result.flags,
        )

    print("Checking request...", file=sys.stderr)
    try:
        state = check_domain(state, model)
    except DomainClassificationError:
        state["domain_ok"] = True
        state.setdefault("guardrail_flags", []).append("domain_classifier_parse_failure")

    if not state["domain_ok"]:
        from core.domain_gate import REFUSAL_MESSAGE

        return (REFUSAL_MESSAGE, state.get("guardrail_flags", []))

    state = route(state)
    if state["path"] == "complex":
        print("Checking request...", file=sys.stderr)
        print("Planning multi-step research...", file=sys.stderr)
        from rag.graph import run_agentic

        final_state = run_agentic(query, model, top_k=top_k)
        answer = final_state.get("answer", "")
        citations = final_state.get("citations", [])
        chunks = final_state.get("retrieved_chunks", [])

        out_result = output_rail(answer, require_citations=bool(chunks))
        flags = state.get("guardrail_flags", []) + out_result.flags

        if not out_result.passed:
            return (
                "[The answer failed output safety/quality checks -- this "
                "usually means retrieved sources were insufficient. Treat "
                "it with caution or try rephrasing.]",
                flags,
            )

        print(answer)
        sources_note = ""
        if chunks:
            sources_note = "Sources:\n" + "\n".join(
                f"  [{c['source_id']}] {c['source']}" + (f" - {c['url']}" if c.get("url") else "")
                for c in chunks
            )
        return (sources_note, flags)

    print("Searching sources...", file=sys.stderr)
    chunks = retrieve(query)
    ranked = rerank(chunks, top_k=top_k, requires_recency=state["requires_recency"])

    print(f"Generating answer from {len(ranked)} sources...", file=sys.stderr)
    print("", file=sys.stderr)  # blank line before streamed tokens start

    def _stream(token: str) -> None:
        print(token, end="", flush=True)

    answer, citations = generate(query, ranked, model, max_tokens=max_tokens, on_token=_stream)
    print("\n", file=sys.stderr)  # separate streamed answer from the rest of the output

    out_result = output_rail(answer, require_citations=bool(ranked))
    flags = state.get("guardrail_flags", []) + out_result.flags

    if not out_result.passed:
        return (
            "[The answer above failed output safety/quality checks -- "
            "this usually means retrieved sources were insufficient. "
            "Treat it with caution or try rephrasing.]",
            flags,
        )

    sources_note = ""
    if ranked:
        sources_note = "Sources:\n" + "\n".join(
            f"  [{c['source_id']}] {c['source']}" + (f" - {c['url']}" if c.get("url") else "")
            for c in ranked
        )

    return (sources_note, flags)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.query:
        print('Fathom\nUsage: fathom "your research question"', file=sys.stderr)
        return 1

    try:
        model = get_model()
    except (ModelNotFoundError, RuntimeError) as exc:
        print(f"Fathom: {exc}", file=sys.stderr)
        return 2

    start = time.monotonic()
    message, flags = run_fast_path(args.query, model, args.max_tokens, args.top_k)
    elapsed = time.monotonic() - start

    print(message)
    if flags:
        print(f"\n[flags: {', '.join(flags)}]", file=sys.stderr)
    print(f"[{elapsed:.1f}s]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

