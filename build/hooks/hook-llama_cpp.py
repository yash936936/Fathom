"""
build/hooks/hook-llama_cpp.py — required PyInstaller hook for
llama-cpp-python.

llama-cpp-python ships a compiled shared library (libllama.so on Linux,
.dylib on macOS, .dll on Windows) as a separate binary artifact
alongside its Python wrapper. PyInstaller's default import scanner only
follows Python-level imports, so it misses this binary entirely --
without this hook, a built executable fails to start with a native
library load error, even though the build itself completes without
warning. This was flagged as a known landmine back when PyInstaller
packaging was first scoped (see docs/appflow.md, docs/decisions.md
D-005), not discovered by trial and error during Phase 8 itself.

PyInstaller auto-discovers hook files named `hook-<module>.py` when
their directory is passed via --additional-hooks-dir (see the
build_<os>.py scripts in this same folder).
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Pulls in the compiled shared library PyInstaller's import scanner
# can't see on its own.
binaries = collect_dynamic_libs("llama_cpp")

# llama-cpp-python also ships some non-Python data files (e.g. default
# chat template files bundled with certain versions) -- collect
# defensively rather than assume there are none.
datas = collect_data_files("llama_cpp")
