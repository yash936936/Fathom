import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from main import _ensure_model_available
from installer_support.model_downloader import ChecksumMismatchError, DownloadError

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


# --- Test 1: model already exists -> no download attempted at all ---
with patch("main.resolve_model_path", return_value=Path("/fake/existing/model.gguf")):
    with patch("pathlib.Path.exists", return_value=True):
        with patch("installer_support.model_downloader.download_model") as mock_download:
            _ensure_model_available()
        check("model already present -> download_model is never called", not mock_download.called)

# --- Test 2: model missing -> download_model is called ---
with patch("main.resolve_model_path", return_value=Path("/fake/missing/model.gguf")):
    with patch("pathlib.Path.exists", return_value=False):
        with patch("installer_support.model_downloader.download_model") as mock_download:
            _ensure_model_available()
        check("model missing -> download_model is called", mock_download.called)
        check("download_model is called with a progress_callback", "progress_callback" in mock_download.call_args.kwargs)

# --- Test 3: progress_callback formats correctly when invoked ---
with patch("main.resolve_model_path", return_value=Path("/fake/missing2/model.gguf")):
    with patch("pathlib.Path.exists", return_value=False):
        captured_callback = {}

        def _capture_download(progress_callback=None, **kwargs):
            captured_callback["cb"] = progress_callback
            progress_callback(500 * 1024 * 1024, 2500 * 1024 * 1024)  # 500MB of 2500MB

        with patch("installer_support.model_downloader.download_model", side_effect=_capture_download):
            _ensure_model_available()
        check("progress_callback was captured and callable", callable(captured_callback.get("cb")))

# --- Test 4: DownloadError from download_model propagates as RuntimeError (caught by main()'s existing except clause) ---
with patch("main.resolve_model_path", return_value=Path("/fake/missing3/model.gguf")):
    with patch("pathlib.Path.exists", return_value=False):
        with patch("installer_support.model_downloader.download_model", side_effect=DownloadError("network broke")):
            raised = None
            try:
                _ensure_model_available()
            except RuntimeError as exc:
                raised = exc
        check("DownloadError propagates as RuntimeError (main()'s except clause catches this)", raised is not None)
        check("propagated error message preserves the original DownloadError text", raised is not None and "network broke" in str(raised))

# --- Test 5: ChecksumMismatchError from download_model also propagates as RuntimeError ---
with patch("main.resolve_model_path", return_value=Path("/fake/missing4/model.gguf")):
    with patch("pathlib.Path.exists", return_value=False):
        with patch("installer_support.model_downloader.download_model", side_effect=ChecksumMismatchError("hash mismatch")):
            raised2 = None
            try:
                _ensure_model_available()
            except RuntimeError as exc:
                raised2 = exc
        check("ChecksumMismatchError propagates as RuntimeError too", raised2 is not None)
        check("propagated error message preserves the original ChecksumMismatchError text", raised2 is not None and "hash mismatch" in str(raised2))

# --- Test 6: main(["--ensure-model"]) works end-to-end, no query needed ---
from main import main as fathom_main

with patch("main.resolve_model_path", return_value=Path("/fake/cli-test/model.gguf")):
    with patch("pathlib.Path.exists", return_value=True):
        exit_code = fathom_main(["--ensure-model"])
    check("main(['--ensure-model']) exits 0 when model already present, no query required", exit_code == 0)

with patch("main.resolve_model_path", return_value=Path("/fake/cli-test2/model.gguf")):
    with patch("pathlib.Path.exists", return_value=False):
        with patch("installer_support.model_downloader.download_model") as mock_dl:
            exit_code2 = fathom_main(["--ensure-model"])
    check("main(['--ensure-model']) triggers download_model when missing", mock_dl.called)
    check("main(['--ensure-model']) exits 0 on successful download", exit_code2 == 0)

with patch("main.resolve_model_path", return_value=Path("/fake/cli-test3/model.gguf")):
    with patch("pathlib.Path.exists", return_value=False):
        with patch("installer_support.model_downloader.download_model", side_effect=DownloadError("simulated failure")):
            exit_code3 = fathom_main(["--ensure-model"])
    check("main(['--ensure-model']) exits 2 on download failure", exit_code3 == 2)

# --- Test 7: --ensure-model bypasses the "no query" early-exit entirely ---
with patch("main.resolve_model_path", return_value=Path("/fake/cli-test4/model.gguf")):
    with patch("pathlib.Path.exists", return_value=True):
        exit_code4 = fathom_main(["--ensure-model"])  # deliberately no query arg
    check("--ensure-model with no query does NOT hit the 'no query' usage error (exit 1)", exit_code4 != 1)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
