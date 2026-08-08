"""
main.py — Fathom CLI entrypoint.

Phase 1 scope only (see docs/phases.md): prove the model loads and
generates via llama-cpp-python within budget. No domain gate, no routing,
no RAG yet -- those land in Phases 2-5. Do not add flags/behavior here
beyond what Phase 1 needs; extend phase-by-phase per docs/workflow.md §4.
"""

from __future__ import annotations

import argparse
import sys
import time

from core.llm_backend import ModelNotFoundError, get_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fathom",
        description="Fathom -- a local, citation-grounded research CLI (Phase 1: raw model smoke test).",
    )
    parser.add_argument("query", nargs="?", help="A prompt to send directly to the model (Phase 1 only -- no guardrails/retrieval yet).")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Max tokens to generate (default: 256).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.query:
        print(
            "Fathom (Phase 1 build -- raw model access only, no guardrails "
            "or retrieval yet)\nUsage: fathom \"your prompt\"",
            file=sys.stderr,
        )
        return 1

    try:
        model = get_model()
    except ModelNotFoundError as exc:
        print(f"Fathom: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Fathom: {exc}", file=sys.stderr)
        return 2

    start = time.monotonic()
    reply = model.chat(
        messages=[{"role": "user", "content": args.query}],
        max_tokens=args.max_tokens,
    )
    elapsed = time.monotonic() - start

    print(reply.strip())
    print(f"\n[{elapsed:.1f}s, n_ctx={model.n_ctx}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
