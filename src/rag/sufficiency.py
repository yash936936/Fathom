"""
rag/sufficiency.py — "enough evidence?" node + retry-loop control.

Per docs/code_logic.md §4 SUFFICIENCY_CHECK node and the
cobusgreyling/loop-engineering pattern adopted in decisions.md D-010:
hard retry cap, and on cap exhaustion the gap is surfaced as an explicit
caveat in the final answer, never silently dropped or silently retried
forever.
"""

from __future__ import annotations

import json

from core.llm_backend import FathomModel
from core.state import ResearchState

MAX_RETRIES = 2  # per code_logic.md §4 -- "2-3 retries then proceed
# best-effort with caveat." Set to the lower end given decisions.md
# D-022's accepted latency cost per retry (another full LLM round trip).

_SYSTEM_PROMPT = """You judge whether retrieved evidence is sufficient \
to answer a research question. Given the question and the evidence \
below, decide if there's enough to give a well-grounded answer.

Respond with ONLY a JSON object, no other text:
{"sufficient": true or false, "gap": "what's missing, if not sufficient, else empty string"}
"""


class SufficiencyCheckError(RuntimeError):
    pass


def _format_evidence_summary(chunks: list) -> str:
    if not chunks:
        return "(no evidence retrieved)"
    return "\n".join(f"- {c['source']}: {c['content'][:150]}" for c in chunks)


def check_sufficiency(query: str, chunks: list, model: FathomModel) -> tuple[bool, str]:
    evidence = _format_evidence_summary(chunks)
    raw = model.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nEvidence:\n{evidence}"},
        ],
        max_tokens=120,
        temperature=0.0,
    )
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
        return bool(parsed["sufficient"]), str(parsed.get("gap", ""))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise SufficiencyCheckError(f"Could not parse sufficiency output: {raw!r}") from exc


def sufficiency_node(state: ResearchState, model: FathomModel) -> ResearchState:
    """Mutates and returns state. Fails open to "sufficient" on parse
    failure -- an unparseable judgment shouldn't trigger an extra retry
    loop (another expensive LLM round trip); better to proceed to
    synthesis and let output-side checks catch a genuinely bad answer.
    """
    try:
        sufficient, gap = check_sufficiency(
            state["original_query"], state.get("retrieved_chunks", []), model
        )
    except SufficiencyCheckError:
        state.setdefault("guardrail_flags", []).append("sufficiency_check_parse_failure")
        state["sufficiency"] = True
        state["sufficiency_gap"] = None
        return state

    state["sufficiency"] = sufficient
    state["sufficiency_gap"] = gap or None
    return state


def should_retry(state: ResearchState) -> bool:
    """The retry-loop gate, per code_logic.md §4: retry only while both
    (a) evidence is judged insufficient AND (b) the hard cap hasn't been
    hit. On cap exhaustion, the caller (rag/graph.py) proceeds to
    synthesis anyway with the gap surfaced as a caveat -- never silently
    loops forever, never silently drops the gap. Matches the
    cobusgreyling/loop-engineering "loop stuck retrying, human never
    notified" anti-pattern this was explicitly designed to avoid.
    """
    return (not state.get("sufficiency", True)) and state.get("retry_count", 0) < MAX_RETRIES
