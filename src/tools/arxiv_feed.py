"""
tools/arxiv_feed.py — arXiv paper search via arXiv's public Atom API.

No API key required (arXiv's export API is open). Directly relevant to
prd.md's "keeping up with latest trends" requirement for research
literature specifically.

Same sandbox caveat as web_search.py: export.arxiv.org isn't reachable
in the environment this was written in -- parsing logic is unit-tested
against a saved sample response instead of the live endpoint.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from core.state import RetrievedChunk
from tools.registry import register_tool

_ARXIV_API_URL = "http://export.arxiv.org/api/query"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_atom(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        title_el = entry.find("atom:title", _ATOM_NS)
        summary_el = entry.find("atom:summary", _ATOM_NS)
        id_el = entry.find("atom:id", _ATOM_NS)
        published_el = entry.find("atom:published", _ATOM_NS)
        entries.append(
            {
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "summary": (summary_el.text or "").strip() if summary_el is not None else "",
                "url": (id_el.text or "").strip() if id_el is not None else "",
                "published": (published_el.text or "")[:10] if published_el is not None else "",
            }
        )
    return entries


def search(query: str, max_results: int = 5, timeout: float = 10.0) -> list[RetrievedChunk]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = requests.get(_ARXIV_API_URL, params=params, timeout=timeout)
    response.raise_for_status()
    entries = _parse_atom(response.text)

    chunks: list[RetrievedChunk] = []
    for i, e in enumerate(entries):
        chunks.append(
            RetrievedChunk(
                source_id=f"arxiv:{i}",
                content=e["summary"],
                source=e["title"],
                url=e["url"],
                date=e["published"] or None,
                relevance_score=None,
            )
        )
    return chunks


@register_tool(name="arxiv_search", description="Search arXiv for recent research papers, sorted by submission date.")
def arxiv_search_tool(query: str, max_results: int = 5) -> list[RetrievedChunk]:
    return search(query, max_results=max_results)
