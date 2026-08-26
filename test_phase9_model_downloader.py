import sys
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, "src")

from installer_support import model_downloader as md

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


def _fake_response(content: bytes, chunk_size=1024, headers=None):
    """Builds a MagicMock standing in for requests.get(..., stream=True)'s
    context-managed response object."""
    resp = MagicMock()
    resp.headers = headers or {"content-length": str(len(content))}
    resp.raise_for_status = MagicMock()

    def iter_content(chunk_size=None):
        for i in range(0, len(content), chunk_size or 1024):
            yield content[i:i + (chunk_size or 1024)]

    resp.iter_content = iter_content
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


with tempfile.TemporaryDirectory() as tmpdir:
    FAKE_CONTENT = b"fake gguf bytes " * 1000  # deterministic, small stand-in
    FAKE_HASH = hashlib.sha256(FAKE_CONTENT).hexdigest()

    # --- Test 1: compute_sha256 matches hashlib directly ---
    tmp_file = Path(tmpdir) / "test_hash.bin"
    tmp_file.write_bytes(FAKE_CONTENT)
    check("compute_sha256 matches hashlib.sha256 directly", md.compute_sha256(tmp_file) == FAKE_HASH)

    # --- Test 2: verify_existing_model — no file present ---
    missing_path = Path(tmpdir) / "does_not_exist.gguf"
    check("verify_existing_model returns False when file is missing", md.verify_existing_model(missing_path) is False)

    # --- Test 3: verify_existing_model — file present, hash matches EXPECTED_SHA256 ---
    with patch.object(md, "EXPECTED_SHA256", FAKE_HASH):
        matching_path = Path(tmpdir) / "matching.gguf"
        matching_path.write_bytes(FAKE_CONTENT)
        check("verify_existing_model returns True when checksum matches", md.verify_existing_model(matching_path) is True)

        wrong_path = Path(tmpdir) / "wrong.gguf"
        wrong_path.write_bytes(b"different content entirely")
        check("verify_existing_model returns False when checksum does not match", md.verify_existing_model(wrong_path) is False)

    # --- Test 4: download_model — happy path, checksum matches, file renamed into place ---
    with patch.object(md, "EXPECTED_SHA256", FAKE_HASH):
        dest = Path(tmpdir) / "downloaded.gguf"
        fake_resp = _fake_response(FAKE_CONTENT)
        progress_calls = []
        with patch("requests.get", return_value=fake_resp):
            result_path = md.download_model(
                dest_path=dest,
                progress_callback=lambda done, total: progress_calls.append((done, total)),
            )
        check("download_model returns the dest_path", result_path == dest)
        check("downloaded file exists at dest_path", dest.exists())
        check("downloaded file content is correct", dest.read_bytes() == FAKE_CONTENT)
        check("no leftover .part file after success", not dest.with_suffix(dest.suffix + ".part").exists())
        check("progress_callback was called at least once", len(progress_calls) > 0)
        check("final progress call shows completion", progress_calls[-1][0] == len(FAKE_CONTENT))

    # --- Test 5: download_model — checksum mismatch is a loud failure, not silent ---
    with patch.object(md, "EXPECTED_SHA256", "0" * 64):  # deliberately wrong
        dest5 = Path(tmpdir) / "mismatch.gguf"
        fake_resp5 = _fake_response(FAKE_CONTENT)
        raised = False
        with patch("requests.get", return_value=fake_resp5):
            try:
                md.download_model(dest_path=dest5)
            except md.ChecksumMismatchError:
                raised = True
        check("checksum mismatch raises ChecksumMismatchError", raised)
        check("checksum mismatch does NOT leave a bad file at dest_path", not dest5.exists())
        check("checksum mismatch does NOT leave a .part file behind either", not dest5.with_suffix(dest5.suffix + ".part").exists())

    # --- Test 6: download_model — network failure cleans up .part, raises DownloadError ---
    with patch.object(md, "EXPECTED_SHA256", FAKE_HASH):
        import requests as _requests_mod
        dest6 = Path(tmpdir) / "network_fail.gguf"
        raised6 = False
        with patch("requests.get", side_effect=_requests_mod.exceptions.ConnectionError("simulated network failure")):
            try:
                md.download_model(dest_path=dest6)
            except md.DownloadError:
                raised6 = True
        check("network failure raises DownloadError", raised6)
        check("network failure leaves no .part file behind", not dest6.with_suffix(dest6.suffix + ".part").exists())

    # --- Test 7: force=False skips download entirely if a valid file already exists ---
    with patch.object(md, "EXPECTED_SHA256", FAKE_HASH):
        dest7 = Path(tmpdir) / "already_valid.gguf"
        dest7.write_bytes(FAKE_CONTENT)
        call_count = {"n": 0}

        def _should_not_be_called(*a, **k):
            call_count["n"] += 1
            raise AssertionError("requests.get should not have been called")

        with patch("requests.get", side_effect=_should_not_be_called):
            result7 = md.download_model(dest_path=dest7, force=False)
        check("force=False skips re-download when a valid file already exists", call_count["n"] == 0)
        check("download_model still returns dest_path when skipping", result7 == dest7)

    # --- Test 8: force=True always re-downloads even if a valid file exists ---
    with patch.object(md, "EXPECTED_SHA256", FAKE_HASH):
        dest8 = Path(tmpdir) / "force_redownload.gguf"
        dest8.write_bytes(FAKE_CONTENT)
        fake_resp8 = _fake_response(FAKE_CONTENT)
        with patch("requests.get", return_value=fake_resp8) as mock_get:
            md.download_model(dest_path=dest8, force=True)
        check("force=True re-downloads even when a valid file already exists", mock_get.called)

    # --- Test 9: default_filename matches core.llm_backend's convention ---
    from core.llm_backend import DEFAULT_MODEL_FILENAME
    check("default_filename() matches core.llm_backend.DEFAULT_MODEL_FILENAME", md.default_filename() == DEFAULT_MODEL_FILENAME)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
