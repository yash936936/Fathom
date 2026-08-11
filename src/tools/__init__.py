"""
tools package -- importing this package registers every built-in tool
(web_search, news_feed, arxiv_feed, vector_store's curated_search,
github_search, reddit_search) via their @register_tool decorators.

This import is required, not cosmetic: tools/registry.py's dispatch()
only knows about a tool once its module has actually been imported
somewhere. Without this, rag/retriever_hybrid.py's dispatch("web_search",
...) etc. would raise KeyError even though the tool file exists on disk
-- see docs/debug.md B-004 for how this was caught.
"""

from tools import (  # noqa: F401
    arxiv_feed,
    github_search,
    news_feed,
    reddit_search,
    vector_store,
    web_search,
)
