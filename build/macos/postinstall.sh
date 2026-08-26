#!/bin/bash
# build/macos/postinstall.sh — Phase 9 (phases.md, decisions.md D-055)
#
# Written for pkgbuild/productbuild's postinstall script contract: run
# automatically (as root) after a .pkg installer has copied files into
# place, receiving standard installer arguments ($1=package path,
# $2=install location, $3=target volume) that this script doesn't need.
#
# Deliberately thin, same reasoning as build/windows/installer.iss:
# the actual model download lives in src/main.py's
# _ensure_model_available() (decisions.md D-055/D-056), triggered here
# via `fathom --ensure-model` -- not reimplemented in shell. One
# download flow, tested once (test_phase9_*.py), not duplicated per
# platform.
#
# NOT yet run on real macOS -- like build_macos.py itself before
# D-053/D-054's GitHub Actions confirmation, this is written to a
# documented, correct contract but hasn't been executed by a real
# .pkg install yet. Needs the same real-hardware confirmation
# treatment.

set -euo pipefail

APP_DIR="/Applications/Fathom.app/Contents/MacOS"
BINARY="$APP_DIR/fathom"

if [ ! -x "$BINARY" ]; then
    echo "postinstall: expected binary not found or not executable at $BINARY" >&2
    # Exit 0 anyway -- per Apple's installer contract, a postinstall
    # script failure can leave the package manager in a confusing
    # half-installed state. The app files are already placed by this
    # point (this script runs AFTER that); a missing/broken binary
    # here is a packaging defect worth surfacing loudly in CI (see
    # .github/workflows/build-macos-linux.yml's own smoke tests, which
    # would have already caught this before a real .pkg was ever
    # built), not something an end user's install should hard-fail on.
    exit 0
fi

# Runs as the installing user, not root, for the same reason
# decisions.md D-055 gives for Windows: the model cache lives under
# the user's own home directory (core/llm_backend.py's
# default_model_dir(): ~/.fathom/models), so a root-owned download
# would leave a model file the actual end user's own `fathom` process
# can't read back later.
LOGGED_IN_USER=$(stat -f "%Su" /dev/console 2>/dev/null || echo "$USER")

echo "Fathom: downloading the model (one-time, ~2.5GB)..."
if ! sudo -u "$LOGGED_IN_USER" "$BINARY" --ensure-model; then
    echo "postinstall: model download failed -- Fathom will retry on first manual launch instead." >&2
    # Same reasoning as above: don't hard-fail the package install
    # over a network hiccup during download. _ensure_model_available()
    # runs this exact same check on every subsequent launch too, so
    # this isn't a lost cause, just deferred to whenever the user next
    # runs `fathom` themselves with (hopefully) working network.
    exit 0
fi

echo "Fathom: model ready."
exit 0
