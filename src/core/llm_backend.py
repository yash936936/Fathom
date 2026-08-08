"""
core/llm_backend.py — single point of contact with the Fathom model
(Qwen3-4B-Instruct-2507, GGUF, Q4_K_M) via llama-cpp-python.

Per docs/architecture.md: every generation call anywhere in the app goes
through this module. Nothing else should import llama_cpp directly.

Per docs/trd.md §1: CPU-only, <6GB total RAM budget. Defaults here are
chosen conservatively (n_ctx, n_threads) rather than maxed out — see
docs/decisions.md D-012 for the specific numbers and why.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable

# llama_cpp is imported lazily inside FathomModel.__init__ rather than at
# module level, so `from core.llm_backend import FathomModel` doesn't
# hard-fail in environments where the (optional, heavy) dependency isn't
# installed yet -- e.g. when only running unit tests against state.py.


class ModelNotFoundError(RuntimeError):
    """Raised when the GGUF weights aren't present at the resolved path.
    Message is written for an end user reading a CLI error, not a stack
    trace -- see appflow.md for the tone this should match."""


DEFAULT_MODEL_FILENAME = "qwen3-4b-instruct-2507-q4_k_m.gguf"

# Conservative default context window. Qwen3-4B-Instruct-2507 supports up
# to 262,144 tokens natively, but KV cache scales with n_ctx and this app
# has to fit inside <6GB total alongside the ~2.4-2.6GB of weights (see
# trd.md §1, decisions.md D-012). 8192 is a starting point for Phase 1 --
# revisit once Phase 1's exit-criteria memory measurement is logged in
# status.md.
DEFAULT_N_CTX = 8192


def default_model_dir() -> Path:
    """User-level cache directory for the model file, per appflow.md /
    decisions.md D-008 (model is downloaded on install, not bundled)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "fathom" / "models"
    # macOS and Linux share this convention for a user-level CLI cache
    return Path.home() / ".fathom" / "models"


def resolve_model_path() -> Path:
    """Resolve the GGUF path: FATHOM_MODEL_PATH env var takes precedence
    (useful for dev/testing with a model in an arbitrary location),
    otherwise the default cache dir from installer_support/
    model_downloader.py's install-time download target."""
    override = os.environ.get("FATHOM_MODEL_PATH")
    if override:
        return Path(override).expanduser()
    return default_model_dir() / DEFAULT_MODEL_FILENAME


class FathomModel:
    """Thin wrapper around llama_cpp.Llama, scoped to exactly what the
    rest of the app needs: a chat-style call and a raw completion call.
    Nothing here should leak llama_cpp-specific types into callers.
    """

    def __init__(
        self,
        model_path: Path | None = None,
        n_ctx: int = DEFAULT_N_CTX,
        n_threads: int | None = None,
        verbose: bool = False,
    ) -> None:
        self.model_path = model_path or resolve_model_path()
        if not self.model_path.exists():
            raise ModelNotFoundError(
                f"Fathom model not found at {self.model_path}\n\n"
                "The model is downloaded automatically during install "
                "(see docs/appflow.md). If you're running from source "
                "during development, either:\n"
                "  1. Set FATHOM_MODEL_PATH to point at a GGUF file, or\n"
                "  2. Download Qwen3-4B-Instruct-2507 (Q4_K_M GGUF) to "
                f"{self.model_path}\n"
            )

        try:
            from llama_cpp import Llama  # local import, see module docstring
        except ImportError as exc:  # pragma: no cover - environment issue
            raise RuntimeError(
                "llama-cpp-python is not installed. Run: "
                "pip install llama-cpp-python"
            ) from exc

        # n_gpu_layers=0 is explicit, not incidental -- trd.md §1 is
        # CPU-only by hard requirement, not just by default.
        #
        # use_mmap=False is also explicit, per decisions.md D-017: on the
        # reference dev machine, memory-mapping the GGUF (llama.cpp's
        # default) meant weight pages were read from disk on-demand
        # during generation, not just once at load. Disabling mmap forces
        # the full file into RAM upfront (slower load, ~60s vs ~68s is
        # actually about the same -- the win is entirely in generation
        # speed) and measured ~2x faster generation in practice. This
        # trades load time for generation time, which is the right trade
        # for a tool that loads once and answers many queries per run.
        self._llama = Llama(
            model_path=str(self.model_path),
            n_ctx=n_ctx,
            n_threads=n_threads or os.cpu_count() or 4,
            n_gpu_layers=0,
            use_mmap=False,
            verbose=verbose,
        )
        self.n_ctx = n_ctx

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
        stop: Iterable[str] | None = None,
    ) -> str:
        """Chat-style call using the model's embedded chat template
        (Qwen3-Instruct ships one; llama-cpp-python applies it
        automatically via create_chat_completion). This is the path
        every other module (domain_gate, planner, synthesis, etc.)
        should use -- not `complete()` -- since it's what the model was
        instruction-tuned against.
        """
        result: dict[str, Any] = self._llama.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=list(stop) if stop else None,
        )
        return result["choices"][0]["message"]["content"]

    def complete(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.2,
        stop: Iterable[str] | None = None,
    ) -> str:
        """Raw completion, no chat template applied. Used sparingly --
        mainly for Phase 1's own smoke test. Prefer chat() elsewhere."""
        result: dict[str, Any] = self._llama(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=list(stop) if stop else None,
        )
        return result["choices"][0]["text"]


_singleton: FathomModel | None = None


def get_model() -> FathomModel:
    """Lazy singleton accessor. Loading the model is expensive (disk I/O
    + several seconds of init) -- every caller in the app should go
    through this rather than constructing FathomModel() directly, so the
    weights are loaded exactly once per process."""
    global _singleton
    if _singleton is None:
        _singleton = FathomModel()
    return _singleton
