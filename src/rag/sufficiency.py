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
{"sufficient": true or false, "gap": "what's missing, if not sufficient, else empty string", "search_query": "a short, specific search-engine-style query (a few words, NOT a sentence) targeting exactly the missing information, if not sufficient, else empty string"}

The "search_query" field will be sent directly to a search engine -- it \
must look like something a person would type into a search box (e.g. \
"small modular reactor 2026 progress"), never a full sentence or an \
explanation of what's missing. If sufficient is false, search_query \
must NOT be empty -- always provide a real search term.

Example of a good response when evidence is insufficient:
{"sufficient": false, "gap": "no sources discuss small modular reactor progress", "search_query": "small modular reactor 2026 news"}
"""

# Common filler/connective words to strip when deriving a fallback query
# from the prose `gap` field -- see decisions.md D-026. Deliberately a
# short, unglamorous list; this is a bounded heuristic, not an NLP
# pipeline, and doesn't need to be exhaustive to be useful.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "does", "do", "did",
    "not", "no", "none", "any", "of", "in", "on", "at", "to", "for",
    "and", "or", "but", "with", "about", "from", "by", "this", "that",
    "these", "those", "it", "its", "as", "be", "been", "being", "have",
    "has", "had", "provided", "evidence", "sources", "source", "given",
    "information", "covered", "cover", "discuss", "discussed", "topic",
    "content", "mentioned", "unrelated", "specific", "specifically",
}


def _fallback_query_from_gap(gap: str, max_words: int = 8) -> str:
    """Cheap, bounded, LLM-free keyword extraction -- used only when the
    model itself failed to produce a usable search_query (empty, or
    rejected for being too long). Better than giving up on refinement
    entirely, and safer than B-006's mistake since it's capped at
    max_words the same way the primary path is validated.
    """
    words = [w.strip(".,!?;:\"'()") for w in gap.lower().split()]
    keywords = [w for w in words if w and w not in _STOPWORDS and len(w) > 2]
    return " ".join(keywords[:max_words])


class SufficiencyCheckError(RuntimeError):
    pass


def _format_evidence_summary(chunks: list) -> str:
    if not chunks:
        return "(no evidence retrieved)"
    return "\n".join(f"- {c['source']}: {c['content'][:150]}" for c in chunks)


def check_sufficiency(query: str, chunks: list, model: FathomModel) -> tuple[bool, str, str]:
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
        return (
            bool(parsed["sufficient"]),
            str(parsed.get("gap", "")),
            str(parsed.get("search_query", "")),
        )
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise SufficiencyCheckError(f"Could not parse sufficiency output: {raw!r}") from exc


def sufficiency_node(state: ResearchState, model: FathomModel) -> ResearchState:
    """Mutates and returns state. Fails open to "sufficient" on parse
    failure -- an unparseable judgment shouldn't trigger an extra retry
    loop (another expensive LLM round trip); better to proceed to
    synthesis and let output-side checks catch a genuinely bad answer.
    """
    try:
        sufficient, gap, search_query = check_sufficiency(
            state["original_query"], state.get("retrieved_chunks", []), model
        )
    except SufficiencyCheckError:
        state.setdefault("guardrail_flags", []).append("sufficiency_check_parse_failure")
        state["sufficiency"] = True
        state["sufficiency_gap"] = None
        state["refined_search_query"] = None
        return state

    state["sufficiency"] = sufficient
    state["sufficiency_gap"] = gap or None

    # Defense in depth against B-006: even with an explicit prompt
    # instruction, the model isn't guaranteed to return something
    # query-shaped rather than a sentence. A crude but effective sanity
    # check -- reject anything that looks like prose (too many words) --
    # since a bad "refined" query actively hurts retrieval (sends noise
    # to search APIs) rather than just being a no-op like an empty one.
    if search_query and len(search_query.split()) <= 8:
        state["refined_search_query"] = search_query
    else:
        state["refined_search_query"] = None
        if search_query:
            state.setdefault("guardrail_flags", []).append("sufficiency_search_query_rejected_not_query_shaped")
        elif not sufficient and gap:
            # Per decisions.md D-026: real-hardware testing showed the
            # model often returns an EMPTY search_query even when
            # correctly told to always provide one -- silently falling
            # back to "no refinement" here would recreate B-005's
            # original problem (retries that don't search for anything
            # new), just without B-006's actively-harmful version. Derive
            # a bounded, LLM-free fallback from `gap` instead of giving up.
            fallback = _fallback_query_from_gap(gap)
            if fallback:
                state["refined_search_query"] = fallback
                state.setdefault("guardrail_flags", []).append("refined_search_query_derived_from_gap_fallback")

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
