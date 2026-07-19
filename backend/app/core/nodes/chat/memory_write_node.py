"""memory_write_node: persists extracted facts into the memory engine.

For each candidate fact from ``extract_facts_node``, delegates to
``app.memory.writer.MemoryWriter.consolidate`` -- which embeds the
content, searches for similar existing notes, and (skipping the decision
LLM call entirely when nothing is similar enough) applies exactly one of
ADD / UPDATE / INVALIDATE / NOOP, with an audit row for each. Attaches
``state["assistant_episode_id"]`` (set by ``write_episodes_node``, which
runs just before this in the graph) as ``source_episode_id`` so notes can
be traced back to the turn that produced them.

Never raises: a DB-unavailable or otherwise-failing write path degrades
to a no-op (logged) rather than failing the chat turn -- the reply has
already been produced and returned to the user by this point in the
graph.
"""

import logging
from typing import Any

from app.core.graph.state import ChatState

logger = logging.getLogger(__name__)


async def memory_write_node(
    state: ChatState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Persist extracted facts as memory notes, applying the writer's dedup decision."""
    candidates = state.get("fact_candidates") or []
    user_id = state.get("user_id")
    if not candidates or not user_id:
        return {}

    try:
        from app.memory.writer import MemoryWriter

        writer = MemoryWriter(user_id)
        results = await writer.consolidate(
            user_id, candidates, state.get("assistant_episode_id")
        )
        return {"memory_write_results": results}
    except Exception:
        logger.warning("Memory write failed; continuing without persisting facts", exc_info=True)
        return {}
