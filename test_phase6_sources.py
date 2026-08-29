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

# --- D-034: shared text_utils.simplify_to_keywords ---
from core.text_utils import simplify_to_keywords

simplified = simplify_to_keywords("What are the latest open source tools for LLM fine-tuning?", max_words=6)
check(
    "simplify_to_keywords turns a real failing query into keyword form",
    simplified == "open tools llm fine-tuning",
)
check("simplify_to_keywords respects max_words cap", len(simplify_to_keywords("one two three four five six seven eight nine ten", max_words=4).split()) == 4)
check("simplify_to_keywords handles all-stopword input without crashing", simplify_to_keywords("what is the") == "")

# --- D-036: arxiv_feed.py now also simplifies queries, same fix as github_search.py ---
q1 = "What are the latest developments in fusion energy research and recent milestones in experimental reactors like ITER, SPARC, or private fusion startups?"
simplified_q1 = simplify_to_keywords(q1, max_words=8)
check(
    "arxiv-style query simplification produces a real keyword query from the exact real failing sub_query",
    simplified_q1 == "fusion energy research milestones experimental reactors iter sparc",
)

# --- D-034: reddit_search removed from retriever_hybrid's default list ---
import inspect
from rag.retriever_hybrid import retrieve as retrieve_fn

source = inspect.getsource(retrieve_fn)
check("reddit_search no longer in the default tool list", '"reddit_search"' not in source.split("all_chunks")[0])
check("github_search still in the default tool list", '"github_search"' in source)

# --- D-063/B-021: github_search.py now self-throttles like arxiv_feed.py.
# Tested by directly exercising _throttle() with a mocked clock, so this
# doesn't actually burn 6 real seconds per test run. ---
import tools.github_search as github_search_module

_fake_now = [0.0]
_sleep_calls = []


def _fake_monotonic():
    return _fake_now[0]


def _fake_sleep(seconds):
    _sleep_calls.append(seconds)
    _fake_now[0] += seconds


_real_monotonic = github_search_module.time.monotonic
_real_sleep = github_search_module.time.sleep
github_search_module.time.monotonic = _fake_monotonic
github_search_module.time.sleep = _fake_sleep
github_search_module._last_call_time = 0.0

github_search_module._throttle()  # first call: no prior call time recorded meaningfully -> may or may not sleep depending on default
check("first _throttle() call does not need a wait beyond the configured interval", _sleep_calls == [] or _sleep_calls[0] <= github_search_module._MIN_INTERVAL_SECONDS)

_sleep_calls.clear()
_fake_now[0] += 1.0  # only 1 second elapsed since the last call
github_search_module._throttle()
check("B-021: second call within the interval sleeps for the remaining time", _sleep_calls == [github_search_module._MIN_INTERVAL_SECONDS - 1.0])

_sleep_calls.clear()
_fake_now[0] += github_search_module._MIN_INTERVAL_SECONDS + 5.0  # plenty of time elapsed
github_search_module._throttle()
check("B-021: call after the interval has fully elapsed does not sleep", _sleep_calls == [])

check("B-021: _MIN_INTERVAL_SECONDS matches GitHub's documented 10 req/min limit (D-031)", github_search_module._MIN_INTERVAL_SECONDS == 6.0)

github_search_module.time.monotonic = _real_monotonic
github_search_module.time.sleep = _real_sleep

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
