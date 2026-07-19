"""write_episodes_node: persists this turn's user+assistant episodes.

Runs inside the chat graph (after ``agent_node``, before
``extract_facts_node``) so the assistant episode's id is available in
state as ``assistant_episode_id`` -- this is the ``source_episode_id``
``memory_write_node`` attaches to any notes it writes from this turn,
letting an audit/inspector trace a note back to the exact turn that
produced it.

Replaces the direct ``episodes_repo`` calls that used to live in
``app.api.routes.chat.post_message``; moving them into the graph is what
makes the episode id available to the memory-write nodes that run later
in the same graph invocation. Degrades silently (logs a warning, returns
``{}``) if the database is unreachable -- same philosophy as every other
node in this graph.
"""

import logging
from typing import Any

from app.core.graph.state import ChatState
from app.core.nodes.chat.utils import last_ai_text, last_human_text

logger = logging.getLogger(__name__)


async def write_episodes_node(
    state: ChatState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Insert the user + assistant ``episodes`` rows for this turn."""
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    if not user_id or not session_id:
        return {}

    messages = state.get("messages", [])
    user_text = last_human_text(messages)
    reply_text = last_ai_text(messages)
    citations = state.get("citations") or []
    memory_citations = state.get("memory_citations") or []

    source_ref: dict[str, Any] = {}
    if citations:
        source_ref["citations"] = citations
    if memory_citations:
        source_ref["memory_citations"] = memory_citations

    try:
        from app.memory.db import episodes_repo

        await episodes_repo.insert_chat_turn_episode(
            user_id=user_id, session_id=session_id, role="user", content=user_text
        )
        assistant_episode_id = await episodes_repo.insert_chat_turn_episode(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=reply_text,
            source_ref=source_ref,
        )
    except Exception:
        logger.warning("Could not write episode rows (DB unavailable?)", exc_info=True)
        return {}

    return {"assistant_episode_id": assistant_episode_id}
