"""
build/build_macos.py — builds the Fathom CLI into a standalone macOS
executable.

MUST be run ON macOS -- PyInstaller does not cross-compile
(decisions.md D-005).

Usage (from repo root, inside the project's venv, with both
requirements.txt AND build/requirements-build.txt installed):
    python build/build_macos.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import run_pyinstaller  # noqa: E402

if __name__ == "__main__":
    run_pyinstaller("macos")
