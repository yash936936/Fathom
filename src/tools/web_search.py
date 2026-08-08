"""
tools/web_search.py — general web search, no API key required.

Per trd.md §1 ("no API key required for core operation"), this uses
DuckDuckGo's HTML endpoint (html.duckduckgo.com/html/) rather than a
paid/keyed search API. This is a deliberate scope choice, not an
oversight -- see docs/decisions.md D-019.

NOTE: this module cannot be network-verified in the sandbox this was
written in (huggingface.co and duckduckgo.com aren't reachable there --
see docs/debug.md B-001 for the same limitation hitting llama-cpp-python
earlier). Parsing logic is verified against a saved sample HTML fixture
instead (see tests/unit/test_web_search.py) -- verify against the live
endpoint on a real machine before treating this as Phase 3-complete.
"""

from __future__ import annotations

from html.parser import HTMLParser

import requests

from core.state import RetrievedChunk
from tools.registry import register_tool

_SEARCH_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = "Mozilla/5.0 (compatible; FathomResearchCLI/0.1)"


class _ResultLinkParser(HTMLParser):
    """Minimal HTML parser extracting DuckDuckGo HTML result links and
    snippets, without a heavier dependency (bs4/lxml). Deliberately
    narrow -- only looks for the specific class names DDG's HTML
    endpoint uses (`result__a` for title/link, `result__snippet` for
    the snippet), not a general-purpose HTML-to-text converter.
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = (attrs_dict.get("class") or "").split()

        if tag == "a" and "result__a" in classes:
            self._current = {"title": "", "url": attrs_dict.get("href", ""), "snippet": ""}
            self._capture_title = True
        elif tag == "a" and "result__snippet" in classes:
            self._capture_snippet = True

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        if self._capture_title:
            self._current["title"] += data
        elif self._capture_snippet:
            self._current["snippet"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            if self._capture_title:
                self._capture_title = False
            elif self._capture_snippet:
                self._capture_snippet = False
                if self._current is not None:
                    self.results.append(self._current)
                    self._current = None


def _parse_results(html: str) -> list[dict[str, str]]:
    parser = _ResultLinkParser()
    parser.feed(html)
    return parser.results


def search(query: str, max_results: int = 5, timeout: float = 10.0) -> list[RetrievedChunk]:
    """Direct callable (not just the registered tool) so it can be unit
    tested / used standalone without going through tools/registry.py's
    dispatch."""
    response = requests.post(
        _SEARCH_URL,
        data={"q": query},
        headers={"User-Agent": _USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    parsed = _parse_results(response.text)[:max_results]

    chunks: list[RetrievedChunk] = []
    for i, r in enumerate(parsed):
        chunks.append(
            RetrievedChunk(
                source_id=f"web:{i}",
                content=r["snippet"].strip(),
                source=r["title"].strip(),
                url=r["url"],
                date=None,  # DDG HTML results don't reliably expose dates
                relevance_score=None,  # unranked at this stage -- rerank.py's job
            )
        )
    return chunks


@register_tool(name="web_search", description="General web search via DuckDuckGo, no API key required.")
def web_search_tool(query: str, max_results: int = 5) -> list[RetrievedChunk]:
    return search(query, max_results=max_results)
