"""load_context_node: first node in the chat graph.

Stamps identity (user_id, session_id) into the graph state so downstream
nodes don't need to thread them through function arguments. This is a
working passthrough today; Week 1+ will extend it to also prime a default
token budget and pull session metadata (e.g. title) if useful.
"""

from typing import Any

from app.core.graph.state import ChatState


def load_context_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stamp user_id/session_id from the run config into state.

    LangGraph passes the ``configurable`` dict supplied at invocation time
    via ``config``. We copy ``user_id``/``session_id`` from there into state
    if they are not already present, so nodes downstream can rely on
    ``state["user_id"]`` / ``state["session_id"]`` unconditionally.
    """
    configurable = (config or {}).get("configurable", {})
    updates: dict[str, Any] = {}

    user_id = state.get("user_id") or configurable.get("user_id")
    session_id = state.get("session_id") or configurable.get("session_id")

    if user_id is not None:
        updates["user_id"] = user_id
    if session_id is not None:
        updates["session_id"] = session_id
    if "token_budget" not in state:
        updates["token_budget"] = 4096

    return updates
