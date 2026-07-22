"""``sessions`` table CRUD (Week 1: replaces the in-process session dict)."""

import uuid
from typing import Any

from sqlalchemy import text

from app.memory.db.engine import get_engine


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "title": row["title"],
        "created_at": row["created_at"],
        "last_active_at": row["last_active_at"],
    }


async def insert_session(user_id: uuid.UUID, title: str | None) -> dict[str, Any]:
    """Create a new session row for ``user_id``, returning the inserted row."""
    engine = get_engine()
    session_id = uuid.uuid4()
    async with engine.engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                INSERT INTO sessions (id, user_id, title)
                VALUES (:id, :user_id, :title)
                RETURNING id, user_id, title, created_at, last_active_at
                """
            ),
            {"id": str(session_id), "user_id": str(user_id), "title": title},
        )
        row = result.mappings().first()
    return _row_to_dict(row)


async def list_sessions(user_id: uuid.UUID) -> list[dict[str, Any]]:
    """List sessions for ``user_id``, most recently active first."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT id, user_id, title, created_at, last_active_at
                FROM sessions WHERE user_id = :user_id
                ORDER BY last_active_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        rows = result.mappings().all()
    return [_row_to_dict(row) for row in rows]


async def get_session(session_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Fetch a single session by id, or ``None`` if it doesn't exist."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, user_id, title, created_at, last_active_at "
                "FROM sessions WHERE id = :id"
            ),
            {"id": str(session_id)},
        )
        row = result.mappings().first()
    return _row_to_dict(row) if row is not None else None


async def touch_session(session_id: uuid.UUID | str) -> None:
    """Bump ``last_active_at`` to now for ``session_id``."""
    engine = get_engine()
    async with engine.engine.begin() as conn:
        await conn.execute(
            text("UPDATE sessions SET last_active_at = now() WHERE id = :id"),
            {"id": str(session_id)},
        )
