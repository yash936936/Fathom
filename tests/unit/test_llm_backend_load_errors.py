import sys
import types
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


def _install_fake_llama_cpp(construct):
    """Injects a fake llama_cpp module into sys.modules so
    `from llama_cpp import Llama` (the real import inside
    FathomModel.__init__) resolves to our test double instead of the
    real, heavy dependency. `construct` is called with the kwargs the
    real Llama() would receive, on every construction attempt."""
    fake_module = types.ModuleType("llama_cpp")

    class FakeLlama:
        def __init__(self, **kwargs):
            construct(kwargs)

    fake_module.Llama = FakeLlama
    sys.modules["llama_cpp"] = fake_module


def _reload_llm_backend():
    sys.modules.pop("core.llm_backend", None)
    import core.llm_backend as m
    return m


import tempfile  # noqa: E402

_tmp_model = tempfile.NamedTemporaryFile(suffix=".gguf", delete=False)
_tmp_model.write(b"not a real gguf, just needs to exist")
_tmp_model.close()
_MODEL_PATH = Path(_tmp_model.name)

# --- Test 1: a construction failure is caught (not left as a bare,
# uncaught exception type) and re-raised as RuntimeError -- this is
# what makes existing `except RuntimeError` callers (golden_set_eval.py,
# watchlist_eval.py, first_run_check.py) actually catch it, unlike the
# real bare ValueError B-025 was filed against. ---
llm_backend = _reload_llm_backend()
_install_fake_llama_cpp(lambda kwargs: (_ for _ in ()).throw(ValueError("Failed to create llama_context")))
try:
    llm_backend.FathomModel(model_path=_MODEL_PATH)
    check("a raw ValueError from Llama() is caught and converted", False)
except RuntimeError as exc:
    check("a raw ValueError from Llama() is caught and converted", True)
    check("the resulting RuntimeError names the original exception type", "ValueError" in str(exc))
    check("the resulting RuntimeError includes actionable guidance (RAM)", "RAM" in str(exc))
except ValueError:
    check("a raw ValueError from Llama() is caught and converted (still a bare ValueError -- BUG)", False)

# --- Test 2 (the actual diagnostic fix): on failure with verbose=False
# (the default), a SECOND attempt is made with verbose=True forced on,
# specifically so llama.cpp's own internal diagnostic logging reaches
# stderr before we give up -- verify the second call actually receives
# verbose=True, not just that a retry happens at all. ---
llm_backend = _reload_llm_backend()
seen_verbose_values = []


def _always_fail(kwargs):
    seen_verbose_values.append(kwargs.get("verbose"))
    raise ValueError("Failed to create llama_context")


_install_fake_llama_cpp(_always_fail)
try:
    llm_backend.FathomModel(model_path=_MODEL_PATH)
except RuntimeError:
    pass
check("exactly two construction attempts made on failure (initial + verbose retry)", len(seen_verbose_values) == 2)
check("first attempt uses the caller's verbose setting (False, the default)", seen_verbose_values and seen_verbose_values[0] is False)
check("second (retry) attempt forces verbose=True", len(seen_verbose_values) == 2 and seen_verbose_values[1] is True)

# --- Test 3: if the caller already passed verbose=True, there is
# nothing to gain from a same-settings retry -- only one attempt should
# be made, failing straight to the RuntimeError. ---
llm_backend = _reload_llm_backend()
seen_verbose_values_2 = []
_install_fake_llama_cpp(lambda kwargs: (seen_verbose_values_2.append(kwargs.get("verbose")), (_ for _ in ()).throw(ValueError("boom")))[1])
try:
    llm_backend.FathomModel(model_path=_MODEL_PATH, verbose=True)
except RuntimeError:
    pass
check("no redundant retry when caller already requested verbose=True", len(seen_verbose_values_2) == 1)

# --- Test 4: success on the first attempt does NOT trigger a second
# construction -- the fix must not change happy-path behavior at all. ---
llm_backend = _reload_llm_backend()
construct_count = [0]


class _SuccessfulLlama:
    def __init__(self, **kwargs):
        construct_count[0] += 1


fake_module = types.ModuleType("llama_cpp")
fake_module.Llama = _SuccessfulLlama
sys.modules["llama_cpp"] = fake_module
model = llm_backend.FathomModel(model_path=_MODEL_PATH)
check("successful load makes exactly one construction attempt", construct_count[0] == 1)
check("successful load still sets self.n_ctx as before", model.n_ctx == llm_backend.DEFAULT_N_CTX)

_MODEL_PATH.unlink(missing_ok=True)
sys.modules.pop("llama_cpp", None)
sys.modules.pop("core.llm_backend", None)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
