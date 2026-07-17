"""``reflections`` persistence (Week 3 sleep-time-compute reflections).

Mirrors ``app.memory.db.notes_repo``'s conventions: every write goes
through ``run_transaction_async`` for CockroachDB serialization-failure
retry, embeddings are formatted via
``app.memory.db.chunks_repo.format_vector_literal``, and array/vector
casts use ``CAST(:x AS TYPE)`` (never ``:x::TYPE`` -- see notes_repo for
why). Each function opens its own short transaction so callers never hold
a DB transaction open across an LLM call.
"""

import uuid
from typing import Any

from sqlalchemy import text

from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async

_REFLECTION_FIELDS = "id, user_id, content, cites, trigger_reason, importance, created_at"


def _row_to_reflection(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "content": row["content"],
        "cites": [str(x) for x in (row["cites"] or [])],
        "trigger_reason": row["trigger_reason"],
        "importance": float(row["importance"]),
        "created_at": row["created_at"],
    }


async def insert_reflection(
    *,
    user_id: uuid.UUID | str,
    content: str,
    cites: list[str],
    trigger_reason: str,
    importance: float,
    embedding: list[float],
) -> dict[str, Any]:
    """Insert a new ``reflections`` row, returning it as a plain dict."""
    engine = get_engine()
    reflection_id = uuid.uuid4()
    params = {
        "id": str(reflection_id),
        "user_id": str(user_id),
        "content": content,
        "cites": [str(x) for x in cites],
        "trigger_reason": trigger_reason,
        "importance": importance,
        "embedding": format_vector_literal(embedding),
    }

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    INSERT INTO reflections
                        (id, user_id, content, cites, trigger_reason, importance, embedding)
                    VALUES
                        (:id, :user_id, :content, CAST(:cites AS UUID[]), :trigger_reason,
                         :importance, CAST(:embedding AS VECTOR))
                    RETURNING {_REFLECTION_FIELDS}
                    """
                ),
                params,
            )
            row = result.mappings().first()
        return _row_to_reflection(row)

    return await run_transaction_async(_do)


async def list_reflections(user_id: uuid.UUID | str, *, limit: int = 50) -> list[dict[str, Any]]:
    """List reflections for ``user_id``, newest first."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_REFLECTION_FIELDS} FROM reflections "
                "WHERE user_id = :user_id ORDER BY created_at DESC LIMIT :limit"
            ),
            {"user_id": str(user_id), "limit": limit},
        )
        rows = result.mappings().all()
    return [_row_to_reflection(row) for row in rows]
