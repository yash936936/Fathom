"""
tools/news_feed.py — recent news via Google News RSS.

No API key required. This is the main lever for prd.md's "daily-updating
trends" requirement outside of academic literature (arxiv_feed.py covers
papers, this covers general news/trend coverage).

Same sandbox caveat as web_search.py / arxiv_feed.py -- unit-tested
against a saved sample RSS response, not the live endpoint, since
news.google.com isn't reachable in this sandbox.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

from core.state import RetrievedChunk
from tools.registry import register_tool

_NEWS_RSS_URL = "https://news.google.com/rss/search"


def _parse_rss(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        desc_el = item.find("description")
        items.append(
            {
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "url": (link_el.text or "").strip() if link_el is not None else "",
                "pubDate": (pubdate_el.text or "").strip() if pubdate_el is not None else "",
                "description": (desc_el.text or "").strip() if desc_el is not None else "",
            }
        )
    return items


def search(query: str, max_results: int = 5, timeout: float = 10.0) -> list[RetrievedChunk]:
    url = f"{_NEWS_RSS_URL}?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    items = _parse_rss(response.text)[:max_results]

    chunks: list[RetrievedChunk] = []
    for i, item in enumerate(items):
        chunks.append(
            RetrievedChunk(
                source_id=f"news:{i}",
                content=item["description"] or item["title"],
                source=item["title"],
                url=item["url"],
                date=item["pubDate"] or None,
                relevance_score=None,
            )
        )
    return chunks


@register_tool(name="news_search", description="Search recent news coverage via Google News RSS.")
def news_search_tool(query: str, max_results: int = 5) -> list[RetrievedChunk]:
    return search(query, max_results=max_results)
