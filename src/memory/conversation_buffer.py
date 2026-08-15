"""
memory/conversation_buffer.py — short-term, single-session conversation
history. Per phases.md Phase 7: "multi-turn conversation within a
session retains context."

Explicitly single-session, in-memory only -- each `py src/main.py`
invocation is a fresh process with no memory of prior runs; persistence
across process restarts is architecture.md's long_term_store.py
extension point (v2), not this. This buffer only exists for the
lifetime of an interactive --chat session (main.py's run_chat_loop()).

Per decisions.md D-041: conversation context is injected into
synthesis ONLY, never into the query used for domain_gate/router/
retrieval -- see that decision for why (router's word-count heuristic
and retrieval keyword-matching would both degrade if fed accumulated
context instead of just the current follow-up).
"""

from __future__ import annotations

from core.state import Citation, ConversationTurn

# Bounds history length -- unbounded history would grow the synthesis
# prompt (and therefore per-call cost, already expensive per D-022)
# indefinitely for diminishing benefit from increasingly old turns.
MAX_TURNS = 6


class ConversationBuffer:
    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self.max_turns = max_turns
        self._turns: list[ConversationTurn] = []

    def add_turn(self, query: str, answer: str, citations: list[Citation] | None = None) -> None:
        self._turns.append(ConversationTurn(query=query, answer=answer, citations=citations or []))
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns :]

    def format_context(self) -> str:
        """Formats recent turns into a short block for synthesis to
        resolve references against. Empty string if there's no history
        yet -- callers should treat that as "no context to inject."
        Answers are truncated per-turn to keep the block from growing
        the prompt excessively on long prior answers.
        """
        if not self._turns:
            return ""
        lines = []
        for turn in self._turns:
            answer_summary = turn.answer[:300]
            lines.append(f"Q: {turn.query}\nA: {answer_summary}")
        return "\n\n".join(lines)

    def __len__(self) -> int:
        return len(self._turns)

    def clear(self) -> None:
        self._turns = []
