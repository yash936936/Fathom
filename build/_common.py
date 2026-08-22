"""
build/_common.py — shared PyInstaller invocation logic for all three
build_<os>.py scripts. Not run directly.

Per decisions.md D-005: PyInstaller cannot cross-compile -- each
build_<os>.py script must be run ON that OS. This module exists so the
three scripts don't triplicate the same command construction; it holds
no OS-specific logic of its own, just the shared plumbing.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Maps the os_name label each build_<os>.py script passes in to what
# platform.system() actually reports on that OS. Used to HARD-BLOCK a
# mismatched run before PyInstaller ever starts -- see B-019 below for
# why this exists: without it, running build_macos.py or build_linux.py
# on Windows silently produces a genuine Windows .exe, places it in a
# folder named dist/macos or dist/linux, and prints a path claiming
# it's the right platform. PyInstaller cannot cross-compile
# (decisions.md D-005) -- this makes that a hard failure instead of a
# silent mislabel.
_EXPECTED_PLATFORM_SYSTEM = {
    "windows": "Windows",
    "macos": "Darwin",
    "linux": "Linux",
}


class WrongPlatformError(RuntimeError):
    """Raised when a build_<os>.py script is run on the wrong OS. See
    B-019 -- this used to fail silently instead of raising at all."""


def run_pyinstaller(os_name: str) -> None:
    actual = platform.system()
    expected = _EXPECTED_PLATFORM_SYSTEM[os_name]
    if actual != expected:
        raise WrongPlatformError(
            f"build_{os_name}.py must be run ON {expected} -- this is "
            f"running on {actual}. PyInstaller cannot cross-compile "
            "(decisions.md D-005). Running this script on the wrong OS "
            "would silently produce a real executable for THIS machine's "
            f"OS ({actual}) while placing it in a folder named "
            f"'dist/{os_name}' and claiming it's a {expected} build -- "
            "see decisions.md B-019 for exactly this failure mode caught "
            "on real hardware. Run this script on an actual "
            f"{expected} machine instead."
        )

    dist_dir = REPO_ROOT / "dist" / os_name
    work_dir = REPO_ROOT / "build" / f"_work_{os_name}"
    spec_dir = REPO_ROOT / "build" / f"_spec_{os_name}"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "fathom",
        # --onedir, not --onefile: see decisions.md D-043 -- a
        # --onefile build re-unpacks itself into a temp dir on EVERY
        # launch, adding real latency to every invocation, not just the
        # first. --onedir pays the extraction cost once, at install/
        # unzip time, instead. Worth it even though this app's own
        # per-query latency (D-022) already dwarfs a few seconds of
        # unpack time -- no reason to add avoidable overhead on top.
        "--onedir",
        "--additional-hooks-dir",
        str(REPO_ROOT / "build" / "hooks"),
        "--paths",
        str(REPO_ROOT / "src"),
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        str(REPO_ROOT / "src" / "main.py"),
    ]

    print(f"[build_{os_name}] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Derived from the ACTUAL OS (platform.system()), not the os_name
    # label -- the guard above means these now always agree, but this
    # stays independent of the label on purpose (see B-019): the bug
    # this fixes was exactly a case of trusting the label over reality.
    exe_name = "fathom.exe" if actual == "Windows" else "fathom"
    exe_path = dist_dir / "fathom" / exe_name
    print()
    print(f"[build_{os_name}] Build complete.")
    print(f"[build_{os_name}] Executable: {exe_path}")
    print(f"[build_{os_name}] --onedir needs the whole folder, not just")
    print(f"[build_{os_name}] the exe -- zip '{dist_dir / 'fathom'}' for distribution.")
