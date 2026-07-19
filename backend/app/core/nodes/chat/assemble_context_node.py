"""assemble_context_node: formats retrieved memory notes for the agent's prompt.

Pure formatting, no I/O: takes ``state["retrieved_memories"]`` (already
retrieved + reinforced by ``retrieve_node``) and produces
``memory_context_block`` -- a distinct "Memory -- what I know about this
user's research so far" block ``agent_node`` injects into the system
prompt alongside (not merged with) the paper-excerpt context blocks -- and
``memory_citations``, the ``{note_id, snippet, score}`` payload persisted
onto the assistant episode and surfaced on ``ChatReply.reply``.
"""

from typing import Any

from app.core.graph.state import ChatState

MEMORY_SNIPPET_MAX_LEN = 160

NO_MEMORY_TEXT = "(No memory notes retrieved for this turn.)"


def format_memory_block(memories: list[dict[str, Any]]) -> str:
    """Render retrieved memory notes as a bulleted context block."""
    if not memories:
        return NO_MEMORY_TEXT
    lines = []
    for memory in memories:
        importance = memory.get("importance", 0.0)
        confidence = memory.get("confidence", 0.0)
        lines.append(
            f"- {memory['content']} (importance={importance:.2f}, confidence={confidence:.2f})"
        )
    return "\n".join(lines)


def build_memory_citations(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the ``{note_id, snippet, score}`` citation payload for retrieved memories."""
    citations = []
    for memory in memories:
        content = memory.get("content", "")
        citations.append(
            {
                "note_id": str(memory["id"]),
                "snippet": content[:MEMORY_SNIPPET_MAX_LEN],
                "score": memory.get("score", 0.0),
            }
        )
    return citations


def assemble_context_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble the memory context block + citations for this turn's reply."""
    memories = state.get("retrieved_memories", []) or []
    return {
        "memory_context_block": format_memory_block(memories),
        "memory_citations": build_memory_citations(memories),
    }
