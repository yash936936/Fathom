"""
core/ui.py — terminal progress display: a single-line spinner (default,
quiet mode) vs full stage-by-stage logging (--verbose).

Per user request: quiet mode shows exactly one line that updates in
place ("<spinner> Retrieving evidence...") and is fully cleared before
the final answer prints -- no leftover processing text mixed in with the
outcome. Verbose mode keeps the original one-line-per-stage behavior
(D-021/D-023) for debugging.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Callable

_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_INTERVAL = 0.08


class Spinner:
    """A background-threaded single-line spinner. The blocking LLM/
    retrieval calls happen on the main thread; this thread just repaints
    the same terminal line so the wait is visibly alive rather than
    silent (see decisions.md D-021 -- silence at these latencies looks
    identical to a hang).

    Usage:
        with Spinner() as spinner:
            spinner.set_stage("Checking request")
            ... blocking work ...
            spinner.set_stage("Retrieving evidence")
            ... blocking work ...
        # line is fully cleared on exit -- nothing left behind
    """

    def __init__(self) -> None:
        self._message = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._max_written = 0  # widest line written so far, for clean erase

    def set_stage(self, message: str) -> None:
        with self._lock:
            self._message = message

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            with self._lock:
                message = self._message
            frame = _FRAMES[i % len(_FRAMES)]
            line = f"{frame} {message}..." if message else frame
            self._max_written = max(self._max_written, len(line))
            sys.stderr.write("\r" + line)
            sys.stderr.flush()
            i += 1
            time.sleep(_INTERVAL)

    def __enter__(self) -> "Spinner":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        # Erase the line completely -- pad with spaces to the widest
        # line ever written, then return cursor to column 0. This is the
        # "remove any and all processing text" requirement -- nothing
        # from the spinner should remain visible once we exit.
        sys.stderr.write("\r" + " " * self._max_written + "\r")
        sys.stderr.flush()


def make_stage_reporter(verbose: bool, spinner: Spinner | None) -> Callable[[str], None]:
    """Returns a callback used throughout main.py / rag/graph.py to
    report the current stage. In verbose mode it prints a new line per
    stage (old D-021/D-023 behavior, useful for debugging). In quiet
    mode it updates the given Spinner's single line instead.
    """
    if verbose:
        def report(message: str) -> None:
            print(message, file=sys.stderr)

        return report

    assert spinner is not None, "quiet mode requires a Spinner instance"

    def report(message: str) -> None:
        spinner.set_stage(message)

    return report
