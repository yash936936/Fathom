import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, "src")

from installer_support import first_run_check as frc
from core.llm_backend import ModelNotFoundError

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


class StubModelSuccess:
    def __init__(self, model_path=None):
        pass

    def chat(self, messages, max_tokens=10, temperature=0.0):
        return "hello"


class StubModelEmptyReply:
    def __init__(self, model_path=None):
        pass

    def chat(self, messages, max_tokens=10, temperature=0.0):
        return "   "  # whitespace-only, should count as empty


class StubModelGenerationFails:
    def __init__(self, model_path=None):
        pass

    def chat(self, messages, max_tokens=10, temperature=0.0):
        raise RuntimeError("simulated generation crash")


# --- Test 1: model not found ---
with patch("core.llm_backend.FathomModel", side_effect=ModelNotFoundError("no model at path")):
    result1 = frc.check_first_run()
check("model-not-found -> success=False", result1.success is False)
check("model-not-found message mentions the model file", "not found" in result1.message.lower())

# --- Test 2: model fails to load (e.g. wrong build, OOM) ---
with patch("core.llm_backend.FathomModel", side_effect=RuntimeError("incompatible build for this CPU")):
    result2 = frc.check_first_run()
check("load failure -> success=False", result2.success is False)
check("load failure message includes the underlying error", "incompatible build" in result2.message)

# --- Test 3: model loads but generation crashes ---
with patch("core.llm_backend.FathomModel", StubModelGenerationFails):
    result3 = frc.check_first_run()
check("generation failure -> success=False", result3.success is False)
check("generation failure message distinguishes 'loaded but failed to generate'", "loaded but failed to generate" in result3.message)
check("generation failure still reports load_seconds (load DID succeed)", result3.load_seconds is not None)

# --- Test 4: model loads and generates, but returns empty output ---
with patch("core.llm_backend.FathomModel", StubModelEmptyReply):
    result4 = frc.check_first_run()
check("empty reply -> success=False", result4.success is False)
check("empty reply message flags the empty response specifically", "empty" in result4.message.lower())

# --- Test 5: full success path ---
with patch("core.llm_backend.FathomModel", StubModelSuccess):
    result5 = frc.check_first_run()
check("full success -> success=True", result5.success is True)
check("success message includes the actual generated reply", "hello" in result5.message)
check("success reports both load_seconds and generation_seconds", result5.load_seconds is not None and result5.generation_seconds is not None)

# --- Test 6: main() CLI wrapper returns correct exit codes ---
with patch("core.llm_backend.FathomModel", StubModelSuccess):
    exit_code_success = frc.main()
check("main() returns 0 on success", exit_code_success == 0)

with patch("core.llm_backend.FathomModel", side_effect=ModelNotFoundError("no model")):
    exit_code_fail = frc.main()
check("main() returns 1 on failure", exit_code_fail == 1)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
