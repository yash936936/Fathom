# Fathom — User Manual

Fathom is a research assistant you run on your own computer. Ask it a
question, and it searches the web and other live sources, then gives
you an answer with sources you can check — like a research assistant
who always shows their work.

No account, no subscription, no sending your questions to a company's
servers. It runs entirely on your PC.

**This version works on Windows only.** Mac and Linux support is
planned for a future release.

---

## 1. Installing Fathom

1. Download `fathom-setup.exe`.
2. Double-click it and follow the installer.
3. The first time it runs, Fathom downloads its "brain" — a ~2.5GB
   file — with a progress bar. This only happens once. Make sure
   you're connected to the internet for this step.
4. Once that's done, you're ready to go. You'll find a "Fathom"
   shortcut in your Start Menu.

**To uninstall:** use the "Uninstall Fathom" shortcut in the Start
Menu, next to the "Fathom" shortcut — same as any other program.

---

## 2. Asking a question

Open a Command Prompt (or PowerShell) window and type:

```
fathom "your question here"
```

For example:

```
fathom "What are the latest developments in solid-state batteries?"
```

Fathom will show a spinner while it works, then print an answer with
numbered source references, like a research paper.

**A typical question takes a few minutes.** Fathom is built to
double-check its work rather than answer instantly — it's designed
for "give me a solid answer," not "give me an answer right now."

---

## 3. What Fathom is good for

Fathom is a **research** tool. Good questions look like:

- "What is CRISPR and what's it currently used for?"
- "Compare lithium-ion and solid-state battery energy density."
- "What's the current state of nuclear fusion research?"
- "What caused the 2008 financial crisis?"

Fathom will politely decline anything outside that lane — it's not a
general chatbot, coding assistant, creative writing tool, or
therapist. If you ask it to write code, tell a joke, or roleplay, it
will tell you that's outside what it does, rather than attempt it
badly.

---

## 4. Reading the answer

Every claim in a Fathom answer is followed by a small reference
number, e.g. "...reached 700 Wh/kg [3]." That number points to a
source Fathom actually retrieved and read — not a guess. If you want
to double check something, you can trace it back to where it came
from.

**A note on trust:** Fathom checks its own citations before showing
you the answer, but this checking isn't perfect yet. If a specific
number or fact really matters for something you're doing, it's
worth a quick second look at the source rather than taking it on
faith. Think of Fathom as a fast, tireless research assistant who's
usually right — not an infallible one.

**If Fathom refuses to answer:** that's deliberate, not a bug. It
means one of:
- Your question wasn't a research question (see section 3), or
- Fathom noticed your question assumes something that isn't true
  (e.g. asking why something "shut down" when it didn't), or
- Fathom genuinely couldn't find enough to answer confidently, and
  is telling you that instead of guessing.

In all three cases, that's Fathom being honest about its limits
rather than making something up.

---

## 5. Useful options

You don't need any of these to use Fathom — plain `fathom "question"`
works fine. These are for when you want more control:

| Type this | To get |
|---|---|
| `fathom --chat` | An ongoing conversation — ask a question, then follow-up questions that remember earlier ones, until you type `exit`. |
| `fathom --mode quick "question"` | A faster, shorter answer — trades some thoroughness for speed. |
| `fathom -v "question"` | The answer, plus a quick summary of how it was produced (useful if something seems off). |
| `fathom --max-tokens 800 "question"` | A longer answer than the default (raise the number for more, lower it for less). |

**Starting a conversation:**
```
fathom --chat
```
Then just type your questions one after another. Type `exit` or
`quit` when you're done.

---

## 6. Things to know before you rely on Fathom

- **It's slow by design.** A thorough answer can take a few minutes.
  This is a deliberate trade — Fathom would rather take its time and
  be right than rush and guess. If you're in a hurry, try `--mode
  quick`.
- **Citation accuracy is a work in progress.** Most citations check
  out, but not all of them yet. Don't stake anything important on a
  single number or quote without a quick look at the source.
- **The "is this question even real" check is still being tuned.**
  Fathom is meant to catch trick questions built on a false premise
  (like "why did X shut down" when it never did) — it catches most
  of them, but not 100% reliably yet. If an answer feels like it's
  taking a strange premise at face value, question it.
- **It needs an internet connection** to search for information, even
  though the "brain" itself runs locally on your machine. Nothing you
  ask gets sent anywhere except the live searches needed to answer it.

---

## 7. Getting help

If something isn't working as expected, or Fathom crashes, please
report it with:
- The exact question you asked
- What happened (copy the error message if there is one)
- Roughly how long it had been running

This helps get it fixed faster than "it didn't work."

---

*Fathom is an independent, open-source project. It is not affiliated
with any AI company's paid products or services.*
