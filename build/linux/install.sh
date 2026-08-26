#!/bin/bash
# build/linux/install.sh — Phase 9 (phases.md, decisions.md D-055)
#
# Deliberately thin, same reasoning as build/windows/installer.iss and
# build/macos/postinstall.sh: copies the --onedir build to a standard
# location and puts `fathom` on PATH. The actual model download lives
# once in src/main.py's _ensure_model_available() (decisions.md
# D-055/D-056), triggered here via `fathom --ensure-model`, not
# reimplemented in shell.
#
# No system package manager integration (.deb/.rpm) -- deliberately
# out of scope for now. This is a plain install script matching how
# many third-party CLI tools ship on Linux (copy to /opt, symlink into
# PATH), not a packaging-format commitment; a .deb/.rpm could wrap
# this same script later without changing where the actual logic
# lives.
#
# NOT yet run on real Linux outside of .github/workflows/
# build-macos-linux.yml's own Tier 1 smoke tests (which build and
# --help/ModelNotFoundError-check the binary, but don't run this
# install script itself). Needs its own real-hardware confirmation
# pass, same as every other platform-specific script in this project.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Assumes this script is run from the repo root (or copied alongside a
# dist/linux/fathom/ build) -- matches how build/build_linux.py's own
# printed output already tells the user where the build ends up.
SOURCE_DIR="${1:-$SCRIPT_DIR/../../dist/linux/fathom}"
INSTALL_DIR="${FATHOM_INSTALL_DIR:-$HOME/.local/share/fathom}"
BIN_DIR="${FATHOM_BIN_DIR:-$HOME/.local/bin}"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "install.sh: build output not found at $SOURCE_DIR" >&2
    echo "  Run 'python build/build_linux.py' first, or pass the build" >&2
    echo "  directory as an argument: ./install.sh /path/to/dist/linux/fathom" >&2
    exit 1
fi

if [ ! -x "$SOURCE_DIR/fathom" ]; then
    echo "install.sh: expected binary not found or not executable at $SOURCE_DIR/fathom" >&2
    exit 1
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR"
# Copy the WHOLE --onedir folder, not just the binary -- same
# reasoning as build/_common.py's own printed reminder for Windows:
# the bundled llama_cpp shared libraries and other dependencies live
# alongside the binary, not inside it.
cp -r "$SOURCE_DIR"/. "$INSTALL_DIR/"

ln -sf "$INSTALL_DIR/fathom" "$BIN_DIR/fathom"

if ! command -v fathom >/dev/null 2>&1; then
    echo "Fathom installed to $INSTALL_DIR"
    echo "Note: $BIN_DIR is not on your PATH. Add this to your shell profile:"
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
fi

echo "Fathom: downloading the model (one-time, ~2.5GB)..."
if ! "$INSTALL_DIR/fathom" --ensure-model; then
    echo "install.sh: model download failed -- Fathom will retry on first launch instead." >&2
    # Same deliberate non-fatal handling as postinstall.sh: the binary
    # itself is correctly installed at this point; a network hiccup
    # during the model download shouldn't make install.sh report
    # overall failure when _ensure_model_available() will simply try
    # again on the user's next `fathom` invocation.
    exit 0
fi

echo "Fathom installed and ready. Run: fathom \"your research question\""
