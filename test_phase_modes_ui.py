import sys
import time
sys.path.insert(0, "src")

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


# --- quick_domain_check heuristics ---
from core.domain_gate import quick_domain_check

check("research question passes quick check", quick_domain_check("What's the latest research on fusion energy?") is True)
check("coding request fails quick check", quick_domain_check("write me a python script to sort a list") is False)
check("poem request fails quick check", quick_domain_check("write a poem about the ocean") is False)
check("roleplay request fails quick check", quick_domain_check("pretend you are a pirate") is False)
check("ambiguous but reasonable query passes (fails open)", quick_domain_check("What's the history of the Python programming language's design?") is True)

# --- Spinner mechanics ---
from core.ui import Spinner, make_stage_reporter

with Spinner() as spinner:
    spinner.set_stage("Testing")
    time.sleep(0.3)  # let it spin a couple frames
    check("spinner thread is alive while active", spinner._thread.is_alive())
check("spinner thread stopped after context exit", not spinner._thread.is_alive())

# --- make_stage_reporter ---
printed = []
verbose_report = make_stage_reporter(verbose=True, spinner=None)

import builtins
_original_print = builtins.print
def _capture_print(*args, **kwargs):
    printed.append(" ".join(str(a) for a in args))
builtins.print = _capture_print
try:
    verbose_report("Some stage")
finally:
    builtins.print = _original_print
check("verbose reporter prints the stage message", any("Some stage" in p for p in printed))

spinner2 = Spinner()
quiet_report = make_stage_reporter(verbose=False, spinner=spinner2)
quiet_report("Another stage")
check("quiet reporter updates spinner message instead of printing", spinner2._message == "Another stage")

try:
    make_stage_reporter(verbose=False, spinner=None)
    check("quiet reporter requires a spinner instance", False)
except AssertionError:
    check("quiet reporter requires a spinner instance", True)

# --- main.py mode wiring (argparse + defaults, no model needed) ---
from main import build_parser, QUICK_MODE_MAX_TOKENS, DEEP_MODE_MAX_TOKENS

args = build_parser().parse_args(["some query"])
check("default mode is deep", args.mode == "deep")
check("default verbose is False", args.verbose is False)
check("default max_tokens is None (resolved later per-mode)", args.max_tokens is None)

args_quick = build_parser().parse_args(["some query", "--mode", "quick"])
check("--mode quick parses correctly", args_quick.mode == "quick")

args_verbose = build_parser().parse_args(["some query", "-v"])
check("-v shorthand sets verbose", args_verbose.verbose is True)

check("QUICK_MODE_MAX_TOKENS is meaningfully smaller than DEEP", QUICK_MODE_MAX_TOKENS < DEEP_MODE_MAX_TOKENS)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
