"""``episodes`` table writes (Week 1: durable per-turn chat history).

Every chat turn writes two rows here (type='chat_turn', role='user'/
'assistant') -- this is the episodic-memory groundwork for Week 2's
extract/write pipeline, and (via ``source_ref``) the persistence
mechanism for assistant-turn citations, since the LangGraph checkpointer
only stores message content, not citation metadata.
"""

import json
import uuid
from typing import Any

from sqlalchemy import text

from app.memory.db.engine import get_engine


async def insert_chat_turn_episode(
    *,
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
    role: str,
    content: str,
    source_ref: dict[str, Any] | None = None,
) -> str:
    """Insert one ``type='chat_turn'`` episode row for a single message."""
    engine = get_engine()
    episode_id = uuid.uuid4()
    async with engine.engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO episodes
                    (id, user_id, session_id, type, role, content, source_ref)
                VALUES
                    (:id, :user_id, :session_id, 'chat_turn', :role, :content,
                     CAST(:source_ref AS JSONB))
                """
            ),
            {
                "id": str(episode_id),
                "user_id": str(user_id),
                "session_id": str(session_id),
                "role": role,
                "content": content,
                "source_ref": json.dumps(source_ref or {}),
            },
        )
    return str(episode_id)


async def list_chat_turn_episodes(session_id: uuid.UUID | str) -> list[dict[str, Any]]:
    """List ``chat_turn`` episodes for a session, oldest first."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT role, content, source_ref, created_at FROM episodes
                WHERE session_id = :session_id AND type = 'chat_turn'
                ORDER BY created_at ASC
                """
            ),
            {"session_id": str(session_id)},
        )
        rows = result.mappings().all()
    return [dict(row) for row in rows]
