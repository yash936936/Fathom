"""
tools/github_search.py — GitHub repository search via the public REST
API, no API key required.

Per decisions.md D-031: unauthenticated GitHub search has a real but
usable rate limit (10 requests/min per IP as of this writing) -- fine
for a single-user local CLI, not fine for anything higher-volume. A
User-Agent header is mandatory (GitHub rejects unauthenticated requests
without one).

Per decisions.md D-034: real-hardware testing showed full natural-
language question queries return ZERO results from GitHub's search --
it wants keyword-style queries, not conversational sentences (the same
lesson from B-006, hitting a different tool). `search()` now simplifies
the query to keywords before sending it, via the shared
core/text_utils.py extractor.

Same sandbox caveat as web_search.py/arxiv_feed.py/news_feed.py --
parsing logic is unit-testable against a saved fixture, not verified
against the live endpoint in this sandbox.
"""

from __future__ import annotations

import requests

from core.state import RetrievedChunk
from core.text_utils import simplify_to_keywords
from tools.registry import register_tool

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_USER_AGENT = "Mozilla/5.0 (compatible; FathomResearchCLI/0.1)"


def _parse_results(payload: dict) -> list[dict]:
    items = payload.get("items", [])
    parsed = []
    for item in items:
        parsed.append(
            {
                "name": item.get("full_name", ""),
                "description": item.get("description") or "",
                "url": item.get("html_url", ""),
                "updated_at": item.get("updated_at", ""),
                "stars": item.get("stargazers_count", 0),
            }
        )
    return parsed


def search(query: str, max_results: int = 5, timeout: float = 10.0) -> list[RetrievedChunk]:
    # Simplify to keywords -- see D-034. Falls back to the original
    # query if simplification strips everything (e.g. a query that's
    # already just a couple of proper nouns) rather than sending an
    # empty string to the API.
    simplified = simplify_to_keywords(query, max_words=6) or query

    response = requests.get(
        _GITHUB_SEARCH_URL,
        params={"q": simplified, "sort": "updated", "order": "desc", "per_page": max_results},
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
        timeout=timeout,
    )
    response.raise_for_status()
    parsed = _parse_results(response.json())[:max_results]

    chunks: list[RetrievedChunk] = []
    for i, r in enumerate(parsed):
        content = r["description"] or "(no description)"
        content += f" [{r['stars']} stars]"
        chunks.append(
            RetrievedChunk(
                source_id=f"github:{i}",
                content=content,
                source=r["name"],
                url=r["url"],
                date=r["updated_at"][:10] or None,
                relevance_score=None,
            )
        )
    return chunks


@register_tool(name="github_search", description="Search GitHub repositories, no API key required.")
def github_search_tool(query: str, max_results: int = 5) -> list[RetrievedChunk]:
    return search(query, max_results=max_results)
