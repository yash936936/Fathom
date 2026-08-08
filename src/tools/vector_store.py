"""
tools/vector_store.py — local curated source store.

Named to match architecture.md's original naming (v1 plan assumed dense
vector search), but see docs/decisions.md D-019: this ships as a
BM25-searchable JSON store in v1, not a dense vector index. Keeping the
module name and the RetrievedChunk-shaped interface stable so a real
dense backend can be swapped in later without touching callers.
"""

from __future__ import annotations

import json
from pathlib import Path

from rank_bm25 import BM25Okapi

from core.state import RetrievedChunk
from tools.registry import register_tool

DEFAULT_STORE_PATH = Path.home() / ".fathom" / "curated_sources.json"


def _tokenize(text: str) -> list[str]:
    """Deliberately simple whitespace/lowercase tokenization -- BM25
    doesn't need anything fancier, and pulling in a full NLP tokenizer
    here would be another dependency this module doesn't need."""
    return text.lower().split()


class CuratedStore:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_STORE_PATH
        self._docs: list[dict] = []
        self._bm25: BM25Okapi | None = None
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            self._docs = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._docs = []
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        if not self._docs:
            self._bm25 = None
            return
        tokenized = [_tokenize(d["content"]) for d in self._docs]
        self._bm25 = BM25Okapi(tokenized)

    def add(self, content: str, source: str, url: str | None = None, date: str | None = None) -> None:
        self._docs.append({"content": content, "source": source, "url": url, "date": date})
        self._rebuild_index()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._docs, indent=2), encoding="utf-8")

    def search(self, query: str, max_results: int = 5) -> list[RetrievedChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:max_results]

        chunks: list[RetrievedChunk] = []
        for rank, idx in enumerate(ranked):
            if scores[idx] <= 0:
                continue  # BM25Okapi's zero-score entries aren't matches, don't pad results with noise
            doc = self._docs[idx]
            chunks.append(
                RetrievedChunk(
                    source_id=f"curated:{idx}",
                    content=doc["content"],
                    source=doc["source"],
                    url=doc.get("url"),
                    date=doc.get("date"),
                    relevance_score=float(scores[idx]),
                )
            )
        return chunks


_singleton: CuratedStore | None = None


def get_store() -> CuratedStore:
    global _singleton
    if _singleton is None:
        _singleton = CuratedStore()
    return _singleton


@register_tool(name="curated_search", description="Search the local curated source store (BM25).")
def curated_search_tool(query: str, max_results: int = 5) -> list[RetrievedChunk]:
    return get_store().search(query, max_results=max_results)
