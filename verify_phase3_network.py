"""
Run this on your real machine (with internet access) to verify the three
network-calling tools actually parse live responses correctly --
test_phase3_manual.py already covers everything else (registry, BM25
store, dedupe, reranker logic) without needing network.

Usage:
    py verify_phase3_network.py

Send the full output back so it can be logged in status.md / debug.md
and Phase 3 can be marked complete (or debugged if something's broken).
"""

import sys
sys.path.insert(0, "src")

from tools import web_search, arxiv_feed, news_feed
from rag.retriever_hybrid import retrieve
from rag.reranker import rerank

TEST_QUERY = "quantum computing breakthrough"

print("=" * 60)
print("Step 1: web_search.py against live DuckDuckGo HTML")
print("=" * 60)
try:
    results = web_search.search(TEST_QUERY, max_results=3)
    print(f"Got {len(results)} results")
    for r in results:
        print(f"  - [{r['source'][:50]}] {r['content'][:80]}")
    if not results:
        print("  WARNING: zero results -- parser may be broken, or DDG changed its HTML")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("Step 2: arxiv_feed.py against live arXiv API")
print("=" * 60)
try:
    results = arxiv_feed.search(TEST_QUERY, max_results=3)
    print(f"Got {len(results)} results")
    for r in results:
        print(f"  - [{r.get('date')}] {r['source'][:80]}")
    if not results:
        print("  WARNING: zero results -- unexpected for a common query like this")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("Step 3: news_feed.py against live Google News RSS")
print("=" * 60)
try:
    results = news_feed.search(TEST_QUERY, max_results=3)
    print(f"Got {len(results)} results")
    for r in results:
        print(f"  - [{r.get('date')}] {r['source'][:80]}")
    if not results:
        print("  WARNING: zero results -- unexpected for a trending topic")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("Step 4: full retriever_hybrid.retrieve() + reranker.rerank()")
print("=" * 60)
try:
    fused = retrieve(TEST_QUERY, max_results_per_tool=3)
    print(f"Fused + deduped: {len(fused)} chunks from all sources combined")
    ranked = rerank(fused, top_k=5, requires_recency=True)
    print(f"After rerank (top 5, recency-weighted):")
    for r in ranked:
        print(f"  - [{r['source_id']}] date={r.get('date')} | {r['source'][:60]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("DONE -- copy this whole output back to report results")
print("=" * 60)
