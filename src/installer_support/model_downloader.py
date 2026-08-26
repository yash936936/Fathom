"""
installer_support/model_downloader.py — Phase 9 (phases.md, appflow.md
§1, decisions.md D-008). Downloads the production model (Qwen3-4B-
Instruct-2507, GGUF, Q4_K_M) to the exact path core/llm_backend.py's
resolve_model_path()/default_model_dir() expect, with progress
reporting and checksum verification, per appflow.md §1's exact spec:
"downloads GGUF (~2.5GB) to user cache dir -> shows progress bar ->
verifies checksum -> runs first_run_check.py sanity load."

Pinned to a specific, VERIFIED source and checksum, not "whatever's
current on the repo's main branch" -- the SHA256 below was confirmed
directly against Hugging Face's file metadata for this exact file
(decisions.md D-055). A checksum mismatch on download means either a
corrupted transfer or the upstream file changed out from under this
pin -- either way, that must be a loud failure, never a silent
"close enough, proceed anyway."
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Callable

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from core.llm_backend import DEFAULT_MODEL_FILENAME, resolve_model_path  # noqa: E402

MODEL_REPO = "unsloth/Qwen3-4B-Instruct-2507-GGUF"
# The repo's actual (mixed-case) filename -- different from
# core.llm_backend.DEFAULT_MODEL_FILENAME, which is lowercased for the
# LOCAL cache path per that module's own convention. Downloaded content
# gets saved under the lowercase local name, not the upstream one, so
# resolve_model_path() finds it without needing to know anything about
# how the upstream repo names its files.
_REMOTE_FILENAME = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{_REMOTE_FILENAME}"

# Verified via Hugging Face's own file metadata for this exact file
# (decisions.md D-055) -- not computed locally, not guessed.
EXPECTED_SHA256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"

# ~2.5GB per Hugging Face's listed file size and appflow.md §1's own
# stated figure -- used only as a sanity/progress-bar reference, NOT
# as a correctness check (the checksum is the actual correctness
# check; file size alone can't catch a corrupted-but-same-length
# download).
APPROX_SIZE_BYTES = 2_500_000_000

_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB per read -- large enough to keep
# HTTP overhead low for a multi-GB transfer, small enough that a
# progress_callback still fires often enough to look live, not frozen.


class ChecksumMismatchError(RuntimeError):
    """Raised when a downloaded (or already-present) file's SHA256
    doesn't match EXPECTED_SHA256. Never silently proceeds past this --
    per this module's docstring, a mismatch always means something is
    wrong, corrupted download or a moved-out-from-under-us upstream
    file, and either way the caller needs to know, not get a working-
    looking-but-wrong model silently loaded later."""


class DownloadError(RuntimeError):
    """Network/IO failure during download -- wraps the underlying
    exception with a message a person running the installer (not a
    developer reading a traceback) can actually act on."""


def compute_sha256(path: Path, chunk_size: int = _CHUNK_SIZE) -> str:
    """Streams the file rather than reading it whole into memory --
    this file is ~2.5GB, and installers commonly run on machines close
    to trd.md §1's stated hardware floor."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify_existing_model(path: Path | None = None) -> bool:
    """True if a file already exists at `path` (default:
    resolve_model_path()) AND its checksum matches EXPECTED_SHA256.
    Lets callers (the installer scripts, or a re-run of this module)
    skip re-downloading ~2.5GB when a valid copy is already there --
    per appflow.md §7's update-flow spec: "model cache re-used if
    compatible, re-downloaded only if model itself changed (checksum
    mismatch triggers re-download)."
    """
    path = path or resolve_model_path()
    if not path.exists():
        return False
    return compute_sha256(path) == EXPECTED_SHA256


def download_model(
    dest_path: Path | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    force: bool = False,
) -> Path:
    """Downloads the model to `dest_path` (default: resolve_model_path()
    -- the exact path core/llm_backend.py's FathomModel already looks
    for), verifying the checksum before returning successfully.

    `progress_callback(bytes_downloaded, total_bytes)`, if given, is
    called periodically during download -- per appflow.md §1's "shows
    progress bar" requirement. `total_bytes` comes from the response's
    Content-Length header when the server provides one, otherwise
    APPROX_SIZE_BYTES as a best-effort fallback so a progress bar still
    has SOMETHING to render against rather than showing nothing.

    Downloads to a `.part` temp file first and only renames to the
    final path after the checksum passes -- an interrupted or corrupted
    download must never leave a bad file at the path FathomModel will
    later try to load from. `force=False` (default) skips the download
    entirely if a valid file already exists at `dest_path` (see
    verify_existing_model) -- `force=True` always re-downloads.

    Raises `DownloadError` on network/IO failure, `ChecksumMismatchError`
    if the downloaded file's hash doesn't match `EXPECTED_SHA256`.
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - environment issue
        raise DownloadError(
            "The 'requests' package is required to download the model. "
            "Run: pip install requests"
        ) from exc

    dest_path = dest_path or resolve_model_path()
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if not force and verify_existing_model(dest_path):
        if progress_callback:
            size = dest_path.stat().st_size
            progress_callback(size, size)
        return dest_path

    part_path = dest_path.with_suffix(dest_path.suffix + ".part")

    try:
        with requests.get(MODEL_URL, stream=True, timeout=30) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or APPROX_SIZE_BYTES)
            downloaded = 0
            with open(part_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
    except requests.RequestException as exc:
        part_path.unlink(missing_ok=True)
        raise DownloadError(
            f"Failed to download the model from {MODEL_URL}: {exc}"
        ) from exc

    actual_hash = compute_sha256(part_path)
    if actual_hash != EXPECTED_SHA256:
        part_path.unlink(missing_ok=True)
        raise ChecksumMismatchError(
            f"Downloaded file's checksum does not match the expected "
            f"value.\n  expected: {EXPECTED_SHA256}\n  got:      {actual_hash}\n"
            f"The download was discarded. This means either the transfer "
            f"was corrupted (try again) or the file at {MODEL_URL} has "
            f"changed since this downloader was last verified against it."
        )

    # Only renamed into place AFTER the checksum passes -- see
    # docstring. os.replace is atomic on both POSIX and Windows (unlike
    # a plain rename on some platforms/filesystems), so a crash between
    # these two lines can never leave a half-renamed file either.
    os.replace(part_path, dest_path)
    return dest_path


def default_filename() -> str:
    """Exposed for the OS-specific installer scripts, so none of them
    need to hardcode the filename separately from
    core.llm_backend.DEFAULT_MODEL_FILENAME."""
    return DEFAULT_MODEL_FILENAME
