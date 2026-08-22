"""
tests/eval/judge_model.py — loads the Phase 10 eval judge model
(Llama-3.1-8B-Instruct, GGUF, Q4_K_M), per decisions.md D-049.

Deliberately lives under tests/eval/, NOT src/, and is never imported
by anything under src/ -- this is dev-time eval tooling only. Keeping
it out of src/ means it can never accidentally end up bundled into
build/'s PyInstaller output (Phase 8) the way anything under src/
could be. The production model (Qwen3-4B, core/llm_backend.py) is
completely untouched by this file.

JudgeModel deliberately mirrors core/llm_backend.FathomModel's chat()
signature exactly (same params, same return type) so it can be passed
anywhere a FathomModel is expected -- specifically,
verification/citation_verifier.py's verify_citations(citations, chunks,
model) only ever calls model.chat(...), so a JudgeModel instance works
as a drop-in for that `model` argument with no changes to
citation_verifier.py itself. Same "one call site, works for either
model" reasoning as D-049's design note.

Sequential loading, not concurrent, per D-049: this project's hardware
budget is <6GB (trd.md §1), same constraint the user confirmed applies
to the eval machine too. citation_accuracy_eval.py's --with-judge mode
loads Qwen3-4B, runs every query's generation + retrieval, explicitly
frees it (del + gc.collect()), THEN loads the judge -- never both
models resident at once.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


class JudgeModelNotFoundError(RuntimeError):
    """Same shape as core/llm_backend.ModelNotFoundError -- a message
    written for a developer running eval from source, with a concrete
    next step, not a bare stack trace."""


DEFAULT_JUDGE_FILENAME = "llama-3.1-8b-instruct-q4_k_m.gguf"

# Same conservative default as core/llm_backend.DEFAULT_N_CTX, for the
# same reason -- KV cache scales with n_ctx, and this only needs to
# hold a citation-verification-style prompt (a handful of claims +
# short source excerpts), not a long research answer.
DEFAULT_N_CTX = 8192


def default_judge_model_dir() -> Path:
    """Deliberately a DIFFERENT directory from
    core/llm_backend.default_model_dir() -- these are two separate
    model files (production model vs. eval-only judge) and should
    never be confused or accidentally overwrite one another."""
    return Path.home() / ".fathom" / "eval-judge-models"


def resolve_judge_model_path() -> Path:
    """FATHOM_JUDGE_MODEL_PATH env var takes precedence, mirroring
    FATHOM_MODEL_PATH's role for the production model -- same pattern,
    separate variable, so setting one never accidentally affects the
    other."""
    override = os.environ.get("FATHOM_JUDGE_MODEL_PATH")
    if override:
        return Path(override).expanduser()
    return default_judge_model_dir() / DEFAULT_JUDGE_FILENAME


class JudgeModel:
    """Thin wrapper around llama_cpp.Llama for the eval judge. See
    module docstring for why this mirrors FathomModel's interface
    rather than subclassing or importing it -- these are two genuinely
    separate models loaded at separate times for separate purposes,
    and keeping them structurally independent (even at the cost of a
    little duplication) means a change to the production model's
    loading logic can never accidentally affect the judge, or vice
    versa.
    """

    def __init__(
        self,
        model_path: Path | None = None,
        n_ctx: int = DEFAULT_N_CTX,
        n_threads: int | None = None,
        verbose: bool = False,
    ) -> None:
        self.model_path = model_path or resolve_judge_model_path()
        if not self.model_path.exists():
            raise JudgeModelNotFoundError(
                f"Eval judge model not found at {self.model_path}\n\n"
                "This is Phase 10 eval-only tooling (decisions.md D-049) "
                "-- it does not affect the production Fathom model at "
                "all. To fetch it:\n"
                "  1. Download a Llama-3.1-8B-Instruct GGUF, Q4_K_M "
                "quant (~4.9GB) -- e.g. from a GGUF quantization repo "
                "such as bartowski/Meta-Llama-3.1-8B-Instruct-GGUF on "
                "Hugging Face.\n"
                f"  2. Save it to {self.model_path}, or\n"
                "  3. Set FATHOM_JUDGE_MODEL_PATH to point at wherever "
                "you already have it.\n"
            )

        try:
            from llama_cpp import Llama  # local import, same reasoning
            # as core/llm_backend.py's FathomModel -- don't hard-fail
            # importing this module just because llama-cpp-python isn't
            # installed yet in an environment that never runs eval.
        except ImportError as exc:  # pragma: no cover - environment issue
            raise RuntimeError(
                "llama-cpp-python is not installed. Run: "
                "pip install llama-cpp-python"
            ) from exc

        # n_gpu_layers=0, use_mmap=False -- same choices as FathomModel,
        # same reasoning (trd.md §1 CPU-only; D-017's measured mmap
        # tradeoff). This is still a <6GB-class machine per the user's
        # own stated constraint for where the judge runs.
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
        on_token: Any = None,
    ) -> str:
        """Identical signature and behavior to
        core/llm_backend.FathomModel.chat() -- see that docstring for
        the on_token streaming behavior, unchanged here. Llama-3.1's
        GGUF ships its own chat template, applied automatically by
        create_chat_completion the same way Qwen3's is."""
        if on_token is None:
            result: dict[str, Any] = self._llama.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=list(stop) if stop else None,
            )
            return result["choices"][0]["message"]["content"]

        chunks: list[str] = []
        stream = self._llama.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=list(stop) if stop else None,
            stream=True,
        )
        for piece in stream:
            delta = piece["choices"][0]["delta"].get("content")
            if delta:
                chunks.append(delta)
                on_token(delta)
        return "".join(chunks)
