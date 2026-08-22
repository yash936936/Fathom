import sys
import platform

sys.path.insert(0, "build")

from _common import run_pyinstaller, WrongPlatformError

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


actual = platform.system()
label_for_actual = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(actual)

# --- Every OS label that does NOT match this machine's actual OS must
# raise WrongPlatformError BEFORE subprocess.run() is ever reached ---
for os_name in ["windows", "macos", "linux"]:
    if os_name == label_for_actual:
        continue  # the matching one would actually try to invoke
        # PyInstaller, which isn't what this test is checking
    try:
        run_pyinstaller(os_name)
        check(f"{os_name} on {actual} -- should have raised, did not", False)
    except WrongPlatformError as e:
        check(f"{os_name} on {actual} correctly blocked", True)
        check(f"{os_name} error message names decisions.md D-005", "D-005" in str(e))
        check(f"{os_name} error message names both the wrong OS and the required one", actual in str(e) and os_name in str(e).lower())

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
