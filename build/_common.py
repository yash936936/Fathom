"""
build/_common.py — shared PyInstaller invocation logic for all three
build_<os>.py scripts. Not run directly.

Per decisions.md D-005: PyInstaller cannot cross-compile -- each
build_<os>.py script must be run ON that OS. This module exists so the
three scripts don't triplicate the same command construction; it holds
no OS-specific logic of its own, just the shared plumbing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_pyinstaller(os_name: str) -> None:
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

    exe_name = "fathom.exe" if os_name == "windows" else "fathom"
    exe_path = dist_dir / "fathom" / exe_name
    print()
    print(f"[build_{os_name}] Build complete.")
    print(f"[build_{os_name}] Executable: {exe_path}")
    print(f"[build_{os_name}] --onedir needs the whole folder, not just")
    print(f"[build_{os_name}] the exe -- zip '{dist_dir / 'fathom'}' for distribution.")
