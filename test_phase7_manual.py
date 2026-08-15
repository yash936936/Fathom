import sys
sys.path.insert(0, "src")

results = []


def check(label, condition):
    results.append((label, condition))
    print(f"{'PASS' if condition else 'FAIL'}: {label}")


from memory.conversation_buffer import ConversationBuffer, MAX_TURNS

# --- basic add/format ---
buf = ConversationBuffer()
check("new buffer is empty", len(buf) == 0)
check("empty buffer formats to empty string", buf.format_context() == "")

buf.add_turn("What is fusion energy?", "Fusion combines light nuclei to release energy.")
check("one turn added", len(buf) == 1)
formatted = buf.format_context()
check("formatted context includes the query", "What is fusion energy?" in formatted)
check("formatted context includes the answer", "Fusion combines light nuclei" in formatted)

# --- multi-turn ---
buf.add_turn("What about fission?", "Fission splits heavy nuclei.")
check("two turns tracked", len(buf) == 2)
formatted2 = buf.format_context()
check("both turns appear in formatted context", "fusion energy" in formatted2.lower() and "fission" in formatted2.lower())

# --- max_turns trimming ---
small_buf = ConversationBuffer(max_turns=2)
small_buf.add_turn("Q1", "A1")
small_buf.add_turn("Q2", "A2")
small_buf.add_turn("Q3", "A3")
check("buffer trims to max_turns", len(small_buf) == 2)
trimmed_context = small_buf.format_context()
check("oldest turn dropped after trimming", "Q1" not in trimmed_context)
check("newest turns retained after trimming", "Q2" in trimmed_context and "Q3" in trimmed_context)

# --- long answer truncation in formatting ---
long_answer_buf = ConversationBuffer()
long_answer_buf.add_turn("Q", "A" * 500)
formatted_long = long_answer_buf.format_context()
check("long answers are truncated in formatted context, not included in full", len(formatted_long) < 500)

# --- clear ---
buf.clear()
check("clear() empties the buffer", len(buf) == 0)

# --- default MAX_TURNS constant is reasonable ---
check("default MAX_TURNS is a small positive bound", 0 < MAX_TURNS <= 20)

# --- synthesis.generate threads conversation_context correctly ---
from rag.synthesis import generate
from core.state import RetrievedChunk


class StubModel:
    def __init__(self):
        self.last_messages = None

    def chat(self, messages, max_tokens=200, temperature=0.3, stop=None, on_token=None):
        self.last_messages = messages
        return "An answer [web:0]."


chunks = [RetrievedChunk(source_id="web:0", content="some content", source="s", url=None, date=None, relevance_score=None)]
model = StubModel()
answer, citations = generate("follow-up question", chunks, model, conversation_context="Q: earlier question\nA: earlier answer")
user_message = model.last_messages[1]["content"]
check("conversation_context appears in the actual prompt sent to the model", "earlier question" in user_message and "earlier answer" in user_message)

model2 = StubModel()
generate("a question", chunks, model2, conversation_context="")
user_message2 = model2.last_messages[1]["content"]
check("empty conversation_context adds no context block to the prompt", "Conversation so far" not in user_message2)

print()
n_pass = sum(1 for _, ok in results if ok)
print(f"{n_pass}/{len(results)} checks passed")
if n_pass != len(results):
    sys.exit(1)
