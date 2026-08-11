"""
tools/reddit_search.py — Reddit post search via the public .json search
endpoint, no API key required.

Per decisions.md D-031: Reddit's old.reddit.com/www.reddit.com JSON
endpoints work without OAuth for read-only search, but are rate-limited
and require a descriptive User-Agent (generic ones get 429'd quickly).
This is a real, if fragile, no-key option -- more fragile than the
arXiv/GitHub APIs since it's not an officially documented public API
surface, just a JSON view that happens to work. Flagged here rather
than presented as equally durable.

Same sandbox caveat as the other tool modules -- unverified against the
live endpoint in this sandbox.
"""

from __future__ import annotations

import requests

from core.state import RetrievedChunk
from tools.registry import register_tool

_REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
_USER_AGENT = "FathomResearchCLI/0.1 (by /u/fathom-research-tool)"


def _parse_results(payload: dict) -> list[dict]:
    children = payload.get("data", {}).get("children", [])
    parsed = []
    for child in children:
        data = child.get("data", {})
        parsed.append(
            {
                "title": data.get("title", ""),
                "selftext": data.get("selftext", ""),
                "subreddit": data.get("subreddit_name_prefixed", ""),
                "url": "https://www.reddit.com" + data.get("permalink", ""),
                "created_utc": data.get("created_utc"),
                "score": data.get("score", 0),
            }
        )
    return parsed


def search(query: str, max_results: int = 5, timeout: float = 10.0) -> list[RetrievedChunk]:
    response = requests.get(
        _REDDIT_SEARCH_URL,
        params={"q": query, "sort": "relevance", "limit": max_results, "t": "year"},
        headers={"User-Agent": _USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    parsed = _parse_results(response.json())[:max_results]

    chunks: list[RetrievedChunk] = []
    for i, r in enumerate(parsed):
        content = r["selftext"][:400] if r["selftext"] else r["title"]
        content += f" [{r['score']} upvotes, {r['subreddit']}]"
        date = None
        if r["created_utc"]:
            import datetime

            date = datetime.datetime.utcfromtimestamp(r["created_utc"]).strftime("%Y-%m-%d")
        chunks.append(
            RetrievedChunk(
                source_id=f"reddit:{i}",
                content=content,
                source=r["title"],
                url=r["url"],
                date=date,
                relevance_score=None,
            )
        )
    return chunks


@register_tool(name="reddit_search", description="Search Reddit posts, no API key required (fragile -- unofficial JSON endpoint).")
def reddit_search_tool(query: str, max_results: int = 5) -> list[RetrievedChunk]:
    return search(query, max_results=max_results)
