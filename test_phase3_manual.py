import sys
sys.path.insert(0, "src")

import tools  # noqa: F401 -- registers all built-in tools, see tools/__init__.py

from tools.registry import register_tool, dispatch, list_tools
from tools.vector_store import CuratedStore
from rag.retriever_hybrid import dedupe
from rag.reranker import rerank
from core.state import RetrievedChunk
from datetime import datetime, timezone, timedelta
import tempfile
from pathlib import Path

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


# --- Test 1: registry register + dispatch ---
@register_tool(name="_test_tool", description="test")
def _test_fn(query, max_results=5):
    return [RetrievedChunk(source_id="t:0", content=f"result for {query}", source="test", url=None, date=None, relevance_score=1.0)]

out = dispatch("_test_tool", query="hello", max_results=3)
check("registry dispatch works", len(out) == 1 and out[0]["content"] == "result for hello")

try:
    dispatch("_nonexistent_tool", query="x")
    check("dispatch raises on unknown tool", False)
except KeyError:
    check("dispatch raises on unknown tool", True)

names = [t.name for t in list_tools()]
check("list_tools includes real tools registered at import time", "web_search" in names and "arxiv_search" in names and "news_search" in names and "curated_search" in names)

# --- Test 2: CuratedStore BM25 search ---
with tempfile.TemporaryDirectory() as d:
    store = CuratedStore(path=Path(d) / "store.json")
    store.add("Fusion energy uses hydrogen isotopes to release energy", source="doc1")
    store.add("Quantum computing uses qubits for parallel computation", source="doc2")
    store.add("The stock market fluctuates based on economic indicators", source="doc3")

    hits = store.search("fusion energy hydrogen")
    check("BM25 search finds most relevant doc first", len(hits) > 0 and hits[0]["source"] == "doc1")

    no_hits = store.search("completely unrelated gibberish xyzzy")
    check("BM25 search returns nothing for zero-overlap query", len(no_hits) == 0)

    store.save()
    reloaded = CuratedStore(path=Path(d) / "store.json")
    check("CuratedStore persists and reloads", len(reloaded._docs) == 3)

# --- Test 3: dedupe ---
chunks = [
    RetrievedChunk(source_id="a", content="same text", source="Source A", url=None, date=None, relevance_score=1.0),
    RetrievedChunk(source_id="b", content="same text", source="Source A", url=None, date=None, relevance_score=1.0),
    RetrievedChunk(source_id="c", content="different text", source="Source A", url=None, date=None, relevance_score=1.0),
]
deduped = dedupe(chunks)
check("dedupe drops exact (source, content) duplicates", len(deduped) == 2)

# --- Test 4: reranker recency boost ---
recent_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
old_date = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")

chunks = [
    RetrievedChunk(source_id="old", content="old but high base score", source="s", url=None, date=old_date, relevance_score=1.0),
    RetrievedChunk(source_id="new", content="new with same base score", source="s", url=None, date=recent_date, relevance_score=1.0),
]
ranked_no_recency = rerank(chunks, requires_recency=False)
ranked_with_recency = rerank(chunks, requires_recency=True)

check("without requires_recency, order unaffected by date (tie stays stable)", ranked_no_recency[0]["source_id"] == "old")
check("with requires_recency, recent result is boosted above older equal-score result", ranked_with_recency[0]["source_id"] == "new")

# --- Test 5: reranker top_k truncation ---
many_chunks = [RetrievedChunk(source_id=str(i), content=f"c{i}", source="s", url=None, date=None, relevance_score=float(i)) for i in range(20)]
top5 = rerank(many_chunks, top_k=5)
check("reranker respects top_k", len(top5) == 5)
check("reranker sorts descending by score", top5[0]["source_id"] == "19")

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
