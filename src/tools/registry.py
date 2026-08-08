"""
tools/registry.py — common schema every tool implements, plus dispatch.

Per docs/architecture.md: this is the single abstraction every retrieval
tool (web_search, news_feed, arxiv_feed, vector_store) plugs into, so
rag/planner.py and rag/retriever_hybrid.py can call any tool uniformly
without knowing its internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.state import RetrievedChunk

ToolFn = Callable[..., list[RetrievedChunk]]


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: ToolFn


_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(name: str, description: str):
    """Decorator: registers a tool function under `name`. The function
    must accept `query: str` and return `list[RetrievedChunk]` -- the
    uniform shape every tool normalizes its results into, regardless of
    the underlying source's native response format.
    """

    def decorator(fn: ToolFn) -> ToolFn:
        if name in _REGISTRY:
            raise ValueError(f"Tool '{name}' is already registered")
        _REGISTRY[name] = ToolSpec(name=name, description=description, fn=fn)
        return fn

    return decorator


def list_tools() -> list[ToolSpec]:
    return list(_REGISTRY.values())


def dispatch(name: str, **kwargs) -> list[RetrievedChunk]:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown tool '{name}'. Registered tools: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[name].fn(**kwargs)
