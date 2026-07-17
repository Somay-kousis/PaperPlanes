"""Chat & session endpoints (Week 1: DB-backed sessions/episodes + RAG chat;
Week 2: + memory-note retrieval/citations).

Session metadata (title, timestamps) lives in CockroachDB
(``sessions`` table) via ``app.memory.db.sessions_repo``, replacing the
Week 0 in-process dict. If the database is unreachable, session writes
degrade to a small in-process fallback registry (mirroring the Week 0
behavior) so the echo chat graph keeps working without persistence -- the
same philosophy as the existing checkpointer fallback in ``_get_graph``
below.

Conversation *content* still lives in the LangGraph checkpointer keyed by
``session_id`` as ``thread_id`` (unchanged from Week 0). Per-turn
``episodes`` rows (plus citations/memory_citations, which the
checkpointer doesn't store) are now written *inside* the chat graph itself
(``write_episodes_node``, after the reply is produced) rather than here,
so the assistant episode's id is available in-graph as
``assistant_episode_id`` for the memory-write nodes that run after it.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from app.api.schema.chat import (
    ChatReply,
    ChatReplyMeta,
    Citation,
    MemoryCitation,
    MessageCreate,
    MessageOut,
    SessionCreate,
    SessionListOut,
    SessionOut,
)
from app.core.graph.builder import build_chat_graph
from app.memory.db import episodes_repo, sessions_repo
from app.memory.db.checkpointer import get_checkpointer, reset_checkpointer
from app.memory.db.users_repo import ensure_user, resolve_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["chat"])

# Fallback registry used only when the database is unreachable (Week 0
# behavior, kept as a degraded-mode safety net -- see module docstring).
_SESSIONS_FALLBACK: dict[str, dict[str, Any]] = {}


async def _resolve_and_ensure_user(user_id: str) -> uuid.UUID:
    """Resolve ``user_id`` to its DB UUID, upserting the demo user row.

    The upsert is best-effort: if the DB is unreachable this logs and
    still returns the resolved UUID, so callers can fall back to the
    in-memory registry rather than failing the request outright.
    """
    user_uuid = resolve_user_id(user_id)
    try:
        await ensure_user(user_uuid)
    except Exception:
        logger.warning("Could not upsert user row (DB unavailable?)", exc_info=True)
    return user_uuid


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(payload: SessionCreate) -> SessionOut:
    """Create a new chat session for a user."""
    user_uuid = await _resolve_and_ensure_user(payload.user_id)
    try:
        record = await sessions_repo.insert_session(user_uuid, payload.title)
        return SessionOut(
            id=record["id"],
            user_id=payload.user_id,
            title=record["title"],
            created_at=record["created_at"],
            last_active_at=record["last_active_at"],
        )
    except Exception:
        logger.warning("DB unavailable creating session; using in-memory fallback", exc_info=True)
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        record = {
            "id": session_id,
            "user_id": payload.user_id,
            "title": payload.title,
            "created_at": now,
            "last_active_at": now,
        }
        _SESSIONS_FALLBACK[session_id] = record
        return SessionOut(**record)


@router.get("", response_model=SessionListOut)
async def list_sessions(user_id: str) -> SessionListOut:
    """List sessions belonging to a user, most recently active first."""
    try:
        user_uuid = resolve_user_id(user_id)
        records = await sessions_repo.list_sessions(user_uuid)
        items = [
            SessionOut(
                id=record["id"],
                user_id=user_id,
                title=record["title"],
                created_at=record["created_at"],
                last_active_at=record["last_active_at"],
            )
            for record in records
        ]
        return SessionListOut(items=items)
    except Exception:
        logger.warning("DB unavailable listing sessions; using in-memory fallback", exc_info=True)
        fallback = [
            SessionOut(**s) for s in _SESSIONS_FALLBACK.values() if s["user_id"] == user_id
        ]
        fallback.sort(key=lambda s: s.last_active_at, reverse=True)
        return SessionListOut(items=fallback)


async def _find_session(session_id: str) -> dict[str, Any] | None:
    """Look up a session by id, trying the DB then the in-memory fallback."""
    try:
        record = await sessions_repo.get_session(session_id)
        if record is not None:
            return record
    except Exception:
        logger.warning("DB unavailable looking up session %s", session_id, exc_info=True)
    return _SESSIONS_FALLBACK.get(session_id)


async def _get_graph() -> tuple[Any, bool]:
    """Build a chat graph, using the checkpointer if the DB is reachable.

    Returns ``(graph, persisted)``. Any error acquiring the checkpointer
    (DB down, auth failure, etc.) is caught here and treated as a signal
    to fall back to an unpersisted graph rather than failing the request.
    """
    try:
        checkpointer = await get_checkpointer()
        return build_chat_graph(checkpointer), True
    except Exception:
        logger.warning(
            "Checkpointer unavailable; running chat graph without persistence",
            exc_info=True,
        )
        return build_chat_graph(None), False


async def _run_graph_resiliently(
    graph: Any, persisted: bool, input_state: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Run the chat graph, recovering from a dropped checkpointer connection.

    A DB restart/failover can leave the cached checkpointer holding a closed
    connection, so the first ``ainvoke`` raises ``connection is closed`` at
    graph entry/exit. Rather than 500, we reset the checkpointer (forcing a
    reconnect on the next acquire) and retry once with a fresh graph; if that
    still fails, we fall back to a single unpersisted run so the caller still
    gets a reply (this turn just isn't checkpointed). Returns
    ``(result, persisted)`` -- ``persisted`` reflects whether the run that
    actually produced the result was checkpointed.
    """
    try:
        return await graph.ainvoke(input_state, config=config), persisted
    except Exception:
        logger.warning(
            "Chat graph run failed; resetting checkpointer and retrying once", exc_info=True
        )

    await reset_checkpointer()
    graph, persisted = await _get_graph()
    try:
        return await graph.ainvoke(input_state, config=config), persisted
    except Exception:
        logger.warning(
            "Retry after checkpointer reset failed; running once without persistence",
            exc_info=True,
        )

    return await build_chat_graph(None).ainvoke(input_state, config=config), False


def _message_role(message: Any) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    return str(getattr(message, "type", "unknown"))


def _message_text(message: Any) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: str) -> list[MessageOut]:
    """Return the full message history for a session, from the checkpoint."""
    if await _find_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id!r}")

    graph, persisted = await _get_graph()
    if not persisted:
        # No checkpointer reachable -> no durable history to recover.
        return []

    config = {"configurable": {"thread_id": session_id}}
    try:
        state = await graph.aget_state(config)
    except Exception:
        # A dropped checkpointer connection (DB restart/failover) shouldn't 500
        # a history read: reset so the next request reconnects, and treat this
        # read as "no recoverable history" for now.
        logger.warning("Failed to read session state; resetting checkpointer", exc_info=True)
        await reset_checkpointer()
        return []
    if state is None or not state.values:
        return []

    messages = state.values.get("messages", [])

    # Citations for assistant turns live in `episodes.source_ref`, not the
    # checkpointer. Reconstruct them by zipping assistant-role episodes
    # (oldest first) with assistant messages in order -- each turn's
    # `write_episodes_node` writes exactly one assistant episode per
    # AIMessage appended.
    assistant_source_refs: list[dict[str, Any]] = []
    try:
        turn_episodes = await episodes_repo.list_chat_turn_episodes(session_id)
        assistant_source_refs = [
            episode["source_ref"] or {}
            for episode in turn_episodes
            if episode["role"] == "assistant"
        ]
    except Exception:
        logger.warning("Could not load episodes for citations", exc_info=True)

    out: list[MessageOut] = []
    assistant_i = 0
    for message in messages:
        role = _message_role(message)
        citations = None
        memory_citations = None
        if role == "assistant":
            if assistant_i < len(assistant_source_refs):
                source_ref = assistant_source_refs[assistant_i]
                if source_ref.get("citations"):
                    citations = [Citation(**c) for c in source_ref["citations"]]
                if source_ref.get("memory_citations"):
                    memory_citations = [
                        MemoryCitation(**c) for c in source_ref["memory_citations"]
                    ]
            assistant_i += 1
        out.append(
            MessageOut(
                role=role,
                content=_message_text(message),
                citations=citations,
                memory_citations=memory_citations,
            )
        )
    return out


@router.post("/{session_id}/messages", response_model=ChatReply)
async def post_message(session_id: str, payload: MessageCreate) -> ChatReply:
    """Send a user message, run the chat graph, and return the reply.

    SSE/token streaming is not implemented; this always returns the full
    reply as a single JSON body.
    """
    if await _find_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id!r}")

    user_uuid = await _resolve_and_ensure_user(payload.user_id)

    graph, persisted = await _get_graph()
    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": str(user_uuid),
            "session_id": session_id,
        }
    }
    input_state = {
        "messages": [HumanMessage(content=payload.content)],
        "user_id": str(user_uuid),
        "session_id": session_id,
    }

    result, persisted = await _run_graph_resiliently(graph, persisted, input_state, config)

    reply_message = result["messages"][-1]
    reply_text = _message_text(reply_message)
    used_model = result.get("used_model", "echo")
    rag = result.get("rag", False)
    citations_raw = result.get("citations") or []
    citations = [Citation(**c) for c in citations_raw] if citations_raw else None
    memory_citations_raw = result.get("memory_citations") or []
    memory_citations = (
        [MemoryCitation(**c) for c in memory_citations_raw] if memory_citations_raw else None
    )

    now = datetime.now(UTC)
    try:
        await sessions_repo.touch_session(session_id)
    except Exception:
        if session_id in _SESSIONS_FALLBACK:
            _SESSIONS_FALLBACK[session_id]["last_active_at"] = now

    # Episode rows (with citations/memory_citations in source_ref) are
    # written inside the graph itself by `write_episodes_node`, which runs
    # right after `agent_node` -- see module docstring.

    return ChatReply(
        session_id=session_id,
        reply=MessageOut(
            role="assistant",
            content=reply_text,
            citations=citations,
            memory_citations=memory_citations,
        ),
        meta=ChatReplyMeta(degraded=not persisted, used_model=used_model, rag=rag),
    )
