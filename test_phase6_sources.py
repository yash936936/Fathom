import sys
sys.path.insert(0, "src")

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


import tools  # noqa: F401 -- register everything, confirm no import errors
from tools.registry import list_tools

names = sorted(t.name for t in list_tools())
check("all 6 tools registered including github_search and reddit_search", names == [
    "arxiv_search", "curated_search", "github_search", "news_search", "reddit_search", "web_search"
])

# --- github_search._parse_results against a realistic fixture ---
from tools.github_search import _parse_results as parse_github

github_fixture = {
    "total_count": 1,
    "items": [
        {
            "full_name": "openai/whisper",
            "description": "Robust Speech Recognition via Large-Scale Weak Supervision",
            "html_url": "https://github.com/openai/whisper",
            "updated_at": "2026-08-01T12:00:00Z",
            "stargazers_count": 50000,
        }
    ],
}
parsed = parse_github(github_fixture)
check("github parser extracts repo name", parsed[0]["name"] == "openai/whisper")
check("github parser extracts description", "Speech Recognition" in parsed[0]["description"])
check("github parser extracts star count", parsed[0]["stars"] == 50000)

# missing description shouldn't crash the parser
github_fixture_no_desc = {"items": [{"full_name": "x/y", "description": None, "html_url": "u", "updated_at": "2026-01-01T00:00:00Z", "stargazers_count": 0}]}
parsed_nodesc = parse_github(github_fixture_no_desc)
check("github parser handles null description without crashing", parsed_nodesc[0]["description"] == "")

# --- reddit_search._parse_results against a realistic fixture ---
from tools.reddit_search import _parse_results as parse_reddit

reddit_fixture = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "New fusion breakthrough discussion",
                    "selftext": "Scientists report progress on...",
                    "subreddit_name_prefixed": "r/Physics",
                    "permalink": "/r/Physics/comments/abc123/new_fusion_breakthrough/",
                    "created_utc": 1735689600,
                    "score": 342,
                }
            }
        ]
    }
}
parsed_reddit = parse_reddit(reddit_fixture)
check("reddit parser extracts title", parsed_reddit[0]["title"] == "New fusion breakthrough discussion")
check("reddit parser extracts subreddit", parsed_reddit[0]["subreddit"] == "r/Physics")
check("reddit parser builds full permalink URL", parsed_reddit[0]["url"] == "https://www.reddit.com/r/Physics/comments/abc123/new_fusion_breakthrough/")
check("reddit parser extracts score", parsed_reddit[0]["score"] == 342)

# empty results shouldn't crash
empty_reddit = {"data": {"children": []}}
check("reddit parser handles empty results", parse_reddit(empty_reddit) == [])

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
