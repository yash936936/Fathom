; build/windows/installer.iss — Phase 9 (phases.md, decisions.md D-055)
;
; Deliberately thin: this installer's job is ONLY to place the
; already-built --onedir folder (dist/windows/fathom/, produced by
; build/build_windows.py -- see decisions.md D-043 for why --onedir,
; not --onefile) and create a Start Menu shortcut. It does NOT attempt
; to download the model itself -- src/main.py's own
; _ensure_model_available() (decisions.md D-055/D-056) already handles
; that on first launch, with a live progress line, the exact same code
; path whether Fathom is started by this installer's optional
; "launch after install" checkbox or manually by the user later. One
; download flow, tested once (test_phase9_*.py), not duplicated here
; in Pascal Script.
;
; Compile with the real Inno Setup Compiler (ISCC.exe) on Windows --
; this file is hand-written to valid, documented Inno Setup syntax,
; but like build_windows.py's own PyInstaller invocation, it has not
; been compiled or run yet in this sandbox (no ISCC.exe available
; here). Needs the same "written correctly, not yet real-hardware
; confirmed" treatment as every other platform-specific build script
; in this project until it's actually compiled and run.

#define MyAppName "Fathom"
#define MyAppPublisher "Fathom"
#define MyAppExeName "fathom.exe"
; Sourced from a version file at build time, rather than hardcoded
; here, once Phase 10's release-tagging process (phases.md Phase 10)
; establishes where that version string actually lives. Placeholder
; until then -- update this alongside the first real v1.0 tag.
#define MyAppVersion "1.0.0"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Per-user install by default (no admin elevation needed) -- the model
; cache itself already lives under the user's own profile
; (core/llm_backend.py's default_model_dir(): %LOCALAPPDATA%\fathom\models),
; so there's no reason to require admin rights just to place the
; application binary either.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputBaseFilename=fathom-setup
Compression=lzma2
SolidCompression=yes
; --onedir's output includes llama_cpp's compiled DLLs (see
; build/hooks/hook-llama_cpp.py, confirmed working on real hardware
; per decisions.md D-044) -- ArchitecturesAllowed=x64compatible keeps
; this installer honest about what it actually supports, rather than
; silently offering itself on an architecture the bundled DLLs can't
; run on.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; The whole --onedir output folder, not just the exe -- per
; build/_common.py's own printed reminder ("--onedir needs the whole
; folder, not just the exe"). Source path assumes this .iss is
; compiled from the repo root with dist/windows/fathom/ already built
; by build_windows.py.
Source: "..\..\dist\windows\fathom\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Launches Fathom once after install, with a placeholder query, purely
; to trigger _ensure_model_available()'s first-run download flow as
; part of the install experience -- matches appflow.md §1's stated
; sequence ("installer places binary -> downloads GGUF... -> verifies
; checksum -> runs first_run_check.py sanity load") rather than
; silently deferring the ~2.5GB download to whenever the user happens
; to type their first real question. Unchecked by default
; (Flags: unchecked) -- downloading 2.5GB is a real, noticeable cost
; the user should consciously opt into at install time, not have
; sprung on them.
Filename: "{app}\{#MyAppExeName}"; Parameters: "--ensure-model"; Description: "Download the model now ({#MyAppName} needs ~2.5GB on first run either way)"; Flags: postinstall unchecked runasoriginaluser
