"""
installer_support/first_run_check.py — Phase 9 (phases.md, appflow.md
§1: "...verifies checksum -> runs first_run_check.py sanity load").

A checksum match only proves the BYTES are correct -- it does NOT
prove llama-cpp-python can actually load them on THIS machine (wrong
build for this CPU's instruction set, insufficient RAM, a corrupted
llama-cpp-python install, etc.), or that a loaded model actually
produces output rather than hanging or erroring on first use. Without
this check, any of those failure modes would only surface the first
time the actual end user runs a real research query -- a far worse
place to discover it than during install, where the installer can
still show a clear, actionable error instead of a confusing crash deep
in the app days later.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@dataclass
class FirstRunResult:
    success: bool
    message: str
    load_seconds: float | None = None
    generation_seconds: float | None = None


# Deliberately generic and non-research-flavored -- this is a load/
# generate smoke test, not a quality check (that's citation_accuracy_
# eval.py's job, a completely different concern). Keeping max_tokens
# small keeps this check fast regardless of this project's own
# documented per-call latency variance (decisions.md D-022/D-029) --
# the point is confirming the model produces SOME output, not timing
# it or judging it.
_SANITY_PROMPT = "Reply with exactly one word: hello"
_SANITY_MAX_TOKENS = 10


def check_first_run() -> FirstRunResult:
    """Loads the model via the exact same path the real app uses
    (core.llm_backend.get_model()) and runs one minimal generation.
    Never raises -- every failure mode is caught and returned as a
    FirstRunResult with success=False and an actionable message, since
    the caller here is an installer script, not a developer who wants
    a traceback.
    """
    from core.llm_backend import FathomModel, ModelNotFoundError, resolve_model_path

    model_path = resolve_model_path()
    load_start = time.monotonic()
    try:
        model = FathomModel(model_path=model_path)
    except ModelNotFoundError as exc:
        return FirstRunResult(
            success=False,
            message=(
                f"Model file not found at {model_path} -- "
                f"model_downloader.py should have placed it here before "
                f"this check ran. {exc}"
            ),
        )
    except RuntimeError as exc:
        # llama-cpp-python missing, or (more likely at this stage) a
        # load-time failure from the library itself -- a wrong build
        # for this CPU's instruction set, an out-of-memory condition,
        # or a genuinely corrupted file that happened to pass the
        # checksum (extremely unlikely, but not impossible if the
        # upstream file itself were bad -- this check exists precisely
        # to catch things a checksum can't).
        return FirstRunResult(
            success=False,
            message=f"Model failed to load: {exc}",
        )
    load_seconds = time.monotonic() - load_start

    gen_start = time.monotonic()
    try:
        reply = model.chat(
            messages=[{"role": "user", "content": _SANITY_PROMPT}],
            max_tokens=_SANITY_MAX_TOKENS,
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001 -- ANY generation failure
        # here means "the model loaded but can't actually run," which
        # is exactly the failure mode this check exists to catch
        # before the end user hits it on a real query.
        return FirstRunResult(
            success=False,
            message=f"Model loaded but failed to generate output: {exc}",
            load_seconds=load_seconds,
        )
    generation_seconds = time.monotonic() - gen_start

    if not reply or not reply.strip():
        return FirstRunResult(
            success=False,
            message=(
                "Model loaded and ran but returned an empty response -- "
                "this may indicate a broken build even though loading "
                "succeeded."
            ),
            load_seconds=load_seconds,
            generation_seconds=generation_seconds,
        )

    return FirstRunResult(
        success=True,
        message=f"Model loaded and generated output successfully: {reply.strip()!r}",
        load_seconds=load_seconds,
        generation_seconds=generation_seconds,
    )


def main() -> int:
    result = check_first_run()
    if result.success:
        print(f"OK: {result.message}")
        if result.load_seconds is not None:
            print(f"  load: {result.load_seconds:.1f}s, generation: {result.generation_seconds:.1f}s")
        return 0
    print(f"FAILED: {result.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
