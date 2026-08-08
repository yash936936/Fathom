# appflow.md — End-User Flow

> Redirect: after reading, return to `/context.md` for routing.
> This describes what the USER experiences, not internal logic (see
> `code_logic.md` for that).

## 1. Install
```
User downloads: fathom-setup-<os>.<ext>   (~50-150MB, no model)
User runs installer
  Windows: Inno Setup .exe -> installs to Program Files, adds to PATH
  macOS:   .pkg -> installs binary, runs postinstall.sh
  Linux:   curl | sh -> installs to /usr/local/bin
Installer/postinstall step:
  -> downloads Qwen3-4B-Instruct-2507 GGUF (~2.5GB) to user cache dir
  -> shows progress bar
  -> verifies checksum
  -> runs first_run_check.py sanity load
Install complete message: "fathom is ready. Try: fathom \"your question\""
```
See `phases.md` Phase 9 for build-side detail.

## 2. First run / every run
```
$ fathom "what's the current state of X research"

[domain_gate check — instant, no visible delay if in-domain]
[router decides fast/agentic path — instant]
[if agentic: visible status like "researching... (step 2/3)"]
[answer printed with inline citation markers]
[source list printed below answer]
```

## 3. Off-domain query
```
$ fathom "write me a python script to sort a list"

fathom: This tool is focused on research questions only — it can't
help with coding tasks. Try asking a research/trend/knowledge question instead.
```

## 4. Low-confidence / insufficient evidence
```
$ fathom "<obscure or unanswerable query>"

fathom: I wasn't able to find reliable, verifiable sources for this
question. Rather than guess, I'm flagging this as unanswered. You may want
to try rephrasing, or this may be too recent/niche for current sources.
```

## 5. Offline / no connectivity
```
$ fathom "..."

fathom: Live retrieval is unavailable (no internet connection
detected). I can only answer from previously cached results this session,
and freshness/trend accuracy cannot be guaranteed offline.
```

## 6. Uninstall
```
Windows: Add/Remove Programs -> uninstaller prompts "also remove downloaded
         model files (~2.5GB)?" separately from app removal.
macOS/Linux: uninstall script, same separate prompt for model cache.
```

## 7. Update flow (post v1)
```
New app version released -> user re-runs installer (or update command)
-> app binary replaced -> model cache re-used if compatible, re-downloaded
   only if model itself changed (checksum mismatch triggers re-download)
```

---
**Return to `/context.md` for next steps.**
