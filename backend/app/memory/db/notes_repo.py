"""``memory_notes``/``memory_links`` persistence (Week 2 memory engine).

Every write here goes through ``app.memory.db.retry.run_transaction_async``
so a CockroachDB serialization failure (SQLSTATE 40001) is retried with
backoff rather than surfacing to the caller, mirroring the sync
``run_transaction`` used by ``chunks_repo``'s batch insert but adapted for
the async SQLAlchemy engine everything else in ``app.memory.db`` uses.

Each function opens (and commits) its own short transaction -- consistent
with ``papers_repo``/``sessions_repo``/``episodes_repo`` -- rather than
threading a caller-supplied connection through, which is what keeps every
function here independently mockable in unit tests (see
``tests/unit/test_writer.py``): callers (``app.memory.writer``,
``app.memory.retriever``) never hold a DB transaction open across an LLM
call, they just await a sequence of these calls after the decision is
already made.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async

_NOTE_FIELDS = """
    id, user_id, content, keywords, tags, context, importance, strength,
    last_accessed_at, access_count, confidence, is_user_stated,
    source_episode_id, derived_from, status, valid_at, invalid_at,
    created_at, expired_at
"""


def _row_to_note(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "content": row["content"],
        "keywords": list(row["keywords"] or []),
        "tags": list(row["tags"] or []),
        "context": row["context"],
        "importance": float(row["importance"]),
        "strength": float(row["strength"]),
        "last_accessed_at": row["last_accessed_at"],
        "access_count": int(row["access_count"]),
        "confidence": float(row["confidence"]),
        "is_user_stated": bool(row["is_user_stated"]),
        "source_episode_id": str(row["source_episode_id"]) if row["source_episode_id"] else None,
        "derived_from": [str(x) for x in (row["derived_from"] or [])],
        "status": row["status"],
        "valid_at": row["valid_at"],
        "invalid_at": row["invalid_at"],
        "created_at": row["created_at"],
        "expired_at": row["expired_at"],
    }


_INSERT_NOTE_SQL = f"""
    INSERT INTO memory_notes
        (id, user_id, content, keywords, tags, context, embedding,
         importance, confidence, is_user_stated, source_episode_id,
         derived_from, status)
    VALUES
        (:id, :user_id, :content, :keywords, :tags, :context,
         CAST(:embedding AS VECTOR), :importance, :confidence,
         :is_user_stated, :source_episode_id,
         CAST(:derived_from AS UUID[]), :status)
    RETURNING {_NOTE_FIELDS}
"""

_INSERT_LINK_SQL = """
    INSERT INTO memory_links
        (id, source_note_id, target_note_id, relation_type, weight)
    VALUES (:id, :source, :target, :relation_type, :weight)
"""


def _note_insert_params(
    *,
    user_id: uuid.UUID | str,
    content: str,
    embedding: list[float],
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
    context: str | None = None,
    importance: float = 0.5,
    confidence: float = 0.7,
    is_user_stated: bool = False,
    source_episode_id: uuid.UUID | str | None = None,
    derived_from: list[str] | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """Build the bind params for ``_INSERT_NOTE_SQL`` (also mints the new id)."""
    return {
        "id": str(uuid.uuid4()),
        "user_id": str(user_id),
        "content": content,
        "keywords": list(keywords or []),
        "tags": list(tags or []),
        "context": context,
        "embedding": format_vector_literal(embedding),
        "importance": importance,
        "confidence": confidence,
        "is_user_stated": is_user_stated,
        "source_episode_id": str(source_episode_id) if source_episode_id else None,
        "derived_from": [str(x) for x in (derived_from or [])],
        "status": status,
    }


async def insert_note(
    *,
    user_id: uuid.UUID | str,
    content: str,
    embedding: list[float],
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
    context: str | None = None,
    importance: float = 0.5,
    confidence: float = 0.7,
    is_user_stated: bool = False,
    source_episode_id: uuid.UUID | str | None = None,
    derived_from: list[str] | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """Insert a new ``memory_notes`` row, returning it as a plain dict."""
    engine = get_engine()
    params = _note_insert_params(
        user_id=user_id,
        content=content,
        embedding=embedding,
        keywords=keywords,
        tags=tags,
        context=context,
        importance=importance,
        confidence=confidence,
        is_user_stated=is_user_stated,
        source_episode_id=source_episode_id,
        derived_from=derived_from,
        status=status,
    )

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            result = await conn.execute(text(_INSERT_NOTE_SQL), params)
            row = result.mappings().first()
        return _row_to_note(row)

    return await run_transaction_async(_do)


_SUPERSEDE_OLD_SQL = {
    "archived": (
        "UPDATE memory_notes SET status = 'archived', expired_at = now() WHERE id = :old_id"
    ),
    "invalidated": (
        "UPDATE memory_notes SET status = 'invalidated', invalid_at = now(), "
        "expired_at = now() WHERE id = :old_id"
    ),
}


async def supersede_note(
    old_note_id: uuid.UUID | str,
    *,
    old_status: str,
    new_note: dict[str, Any],
    link_relation: str | None = None,
    link_weight: float = 1.0,
) -> dict[str, Any]:
    """Atomically supersede ``old_note_id`` with a replacement, in ONE transaction.

    Marks the old note (``old_status`` = ``'archived'`` for a refinement, or
    ``'invalidated'`` for a contradiction), inserts the replacement note
    (``new_note`` = the same kwargs ``insert_note`` takes), and -- when
    ``link_relation`` is given -- links new -> old (e.g. ``'contradicts'``). All
    three writes share one transaction, so a failure can't leave the memory
    torn (old gone with no replacement, or a replacement with no link). Retried
    as a unit on serialization failure. Returns the new note dict.
    """
    if old_status not in _SUPERSEDE_OLD_SQL:
        raise ValueError(f"supersede_note: unsupported old_status {old_status!r}")

    engine = get_engine()
    params = _note_insert_params(**new_note)
    new_id = params["id"]
    old_sql = _SUPERSEDE_OLD_SQL[old_status]
    link_params = (
        {
            "id": str(uuid.uuid4()),
            "source": new_id,
            "target": str(old_note_id),
            "relation_type": link_relation,
            "weight": link_weight,
        }
        if link_relation
        else None
    )

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            await conn.execute(text(old_sql), {"old_id": str(old_note_id)})
            result = await conn.execute(text(_INSERT_NOTE_SQL), params)
            row = result.mappings().first()
            if link_params is not None:
                await conn.execute(text(_INSERT_LINK_SQL), link_params)
        return _row_to_note(row)

    return await run_transaction_async(_do)


async def get_note(note_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Fetch a single note by id, or ``None`` if it doesn't exist."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT {_NOTE_FIELDS} FROM memory_notes WHERE id = :id"),
            {"id": str(note_id)},
        )
        row = result.mappings().first()
    return _row_to_note(row) if row is not None else None


async def search_similar_active_notes(
    user_id: uuid.UUID | str, query_embedding: list[float], *, limit: int = 5
) -> list[dict[str, Any]]:
    """ANN search over ACTIVE notes for ``user_id``, accelerated by the vector index.

    Ordered by L2 distance ascending (most similar first); each returned
    dict has a ``"distance"`` key in addition to the usual note fields --
    see ``app.memory.scoring.l2_distance_to_cosine_similarity`` to convert.

    Filters are exactly ``user_id`` + ``status = 'active'`` so they match the
    prefix of the ``(user_id, status, embedding)`` C-SPANN vector index and the
    query is served by an index vector-search rather than a full-table scan
    (verified via EXPLAIN: a residual predicate outside the index prefix -- e.g.
    the temporal ``valid_at``/``invalid_at`` inequalities -- forces CockroachDB
    to fall back to FULL SCAN + top-k). The temporal predicates are omitted here
    deliberately: in the write model ``status`` already encodes current
    validity (a note only gets ``invalid_at``/``expired_at`` set when its status
    leaves ``'active'``, and ``valid_at`` is never future-dated), so at
    query-now time ``status = 'active'`` is equivalent to the full bi-temporal
    predicate. Point-in-time reconstruction (``list_notes(as_of=...)``) still
    applies the temporal columns explicitly -- that's the query that needs them.
    """
    engine = get_engine()
    query_literal = format_vector_literal(query_embedding)
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"""
                SELECT {_NOTE_FIELDS},
                       embedding <-> CAST(:query_vector AS VECTOR) AS distance
                FROM memory_notes
                WHERE user_id = :user_id
                  AND status = 'active'
                ORDER BY embedding <-> CAST(:query_vector AS VECTOR)
                LIMIT :limit
                """
            ),
            {"user_id": str(user_id), "query_vector": query_literal, "limit": limit},
        )
        rows = result.mappings().all()

    notes = []
    for row in rows:
        note = _row_to_note(row)
        note["distance"] = float(row["distance"])
        notes.append(note)
    return notes


async def archive_note(note_id: uuid.UUID | str) -> None:
    """Mark a note ``archived`` (superseded by a refinement), stamping ``expired_at``."""
    engine = get_engine()

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE memory_notes SET status = 'archived', expired_at = now() "
                    "WHERE id = :id"
                ),
                {"id": str(note_id)},
            )

    await run_transaction_async(_do)


async def invalidate_note(note_id: uuid.UUID | str) -> None:
    """Mark a note ``invalidated`` (contradicted), stamping ``invalid_at``/``expired_at``."""
    engine = get_engine()

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE memory_notes SET status = 'invalidated', "
                    "invalid_at = now(), expired_at = now() WHERE id = :id"
                ),
                {"id": str(note_id)},
            )

    await run_transaction_async(_do)


async def reinforce_note(
    note_id: uuid.UUID | str, *, new_strength: float, new_access_count: int
) -> None:
    """Bump a note's ``strength``/``access_count`` and refresh ``last_accessed_at``."""
    engine = get_engine()

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE memory_notes SET strength = :strength, access_count = :count, "
                    "last_accessed_at = now() WHERE id = :id"
                ),
                {"strength": new_strength, "count": new_access_count, "id": str(note_id)},
            )

    await run_transaction_async(_do)


async def insert_link(
    source_note_id: uuid.UUID | str,
    target_note_id: uuid.UUID | str,
    relation_type: str,
    weight: float,
) -> str:
    """Insert a ``memory_links`` row, returning its id."""
    engine = get_engine()
    link_id = uuid.uuid4()
    params = {
        "id": str(link_id),
        "source": str(source_note_id),
        "target": str(target_note_id),
        "relation_type": relation_type,
        "weight": weight,
    }

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO memory_links
                        (id, source_note_id, target_note_id, relation_type, weight)
                    VALUES (:id, :source, :target, :relation_type, :weight)
                    """
                ),
                params,
            )

    await run_transaction_async(_do)
    return str(link_id)


async def list_notes(
    user_id: uuid.UUID | str,
    *,
    status: str | None = "active",
    as_of: datetime | None = None,
    q: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List notes for ``user_id``.

    If ``as_of`` is given, reconstructs transaction-time state as of that
    instant (``created_at <= as_of AND (expired_at IS NULL OR expired_at >
    as_of)``) and ``status`` is ignored -- this answers "what did the
    agent believe at time T", not "what's currently active". Without
    ``as_of``, filters by ``status`` (``None``/``"all"`` means no status
    filter), newest first. ``q`` is an ``ILIKE`` substring filter on
    ``content`` in either mode.
    """
    engine = get_engine()
    clauses = ["user_id = :user_id"]
    params: dict[str, Any] = {"user_id": str(user_id), "limit": limit}

    if as_of is not None:
        clauses.append("created_at <= :as_of AND (expired_at IS NULL OR expired_at > :as_of)")
        params["as_of"] = as_of
    elif status and status != "all":
        clauses.append("status = :status")
        params["status"] = status

    if q:
        clauses.append("content ILIKE :q")
        params["q"] = f"%{q}%"

    where = " AND ".join(clauses)
    order_by = "valid_at DESC" if as_of is not None else "created_at DESC"

    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_NOTE_FIELDS} FROM memory_notes "
                f"WHERE {where} ORDER BY {order_by} LIMIT :limit"
            ),
            params,
        )
        rows = result.mappings().all()
    return [_row_to_note(row) for row in rows]


async def get_links_for_note(note_id: uuid.UUID | str) -> list[dict[str, Any]]:
    """Return links touching ``note_id`` in either direction, with the other note's summary."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT l.id, l.relation_type, l.weight, 'out' AS direction,
                       n.id AS other_id, n.content AS other_content, n.status AS other_status
                FROM memory_links l JOIN memory_notes n ON n.id = l.target_note_id
                WHERE l.source_note_id = :note_id AND l.invalid_at IS NULL
                UNION ALL
                SELECT l.id, l.relation_type, l.weight, 'in' AS direction,
                       n.id AS other_id, n.content AS other_content, n.status AS other_status
                FROM memory_links l JOIN memory_notes n ON n.id = l.source_note_id
                WHERE l.target_note_id = :note_id AND l.invalid_at IS NULL
                """
            ),
            {"note_id": str(note_id)},
        )
        rows = result.mappings().all()
    return [
        {
            "id": str(row["id"]),
            "relation_type": row["relation_type"],
            "weight": float(row["weight"]),
            "direction": row["direction"],
            "other": {
                "id": str(row["other_id"]),
                "content": row["other_content"],
                "status": row["other_status"],
            },
        }
        for row in rows
    ]


async def list_audit(
    *,
    target_id: uuid.UUID | str | None = None,
    action: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List ``memory_audit_log`` rows, newest first, with optional filters."""
    engine = get_engine()
    clauses = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit}

    if target_id is not None:
        clauses.append("target_id = :target_id")
        params["target_id"] = str(target_id)
    if action is not None:
        clauses.append("action = :action")
        params["action"] = action
    if since is not None:
        clauses.append("created_at >= :since")
        params["since"] = since

    where = " AND ".join(clauses)
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"""
                SELECT id, user_id, actor, action, target_table, target_id, reason,
                       details, created_at
                FROM memory_audit_log WHERE {where}
                ORDER BY created_at DESC LIMIT :limit
                """
            ),
            params,
        )
        rows = result.mappings().all()
    return [
        {
            "id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "actor": row["actor"],
            "action": row["action"],
            "target_table": row["target_table"],
            "target_id": str(row["target_id"]),
            "reason": row["reason"],
            "details": row["details"] or {},
            "created_at": row["created_at"],
        }
        for row in rows
    ]


async def stats(user_id: uuid.UUID | str) -> dict[str, Any]:
    """Aggregate note/audit/link counts for the memory-inspector dashboard."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        notes_result = await conn.execute(
            text(
                "SELECT status, count(*) AS n FROM memory_notes "
                "WHERE user_id = :user_id GROUP BY status"
            ),
            {"user_id": str(user_id)},
        )
        notes_by_status = {row["status"]: int(row["n"]) for row in notes_result.mappings().all()}

        audit_result = await conn.execute(
            text(
                """
                SELECT action, count(*) AS n FROM memory_audit_log
                WHERE user_id = :user_id AND created_at >= now() - INTERVAL '24 hours'
                GROUP BY action
                """
            ),
            {"user_id": str(user_id)},
        )
        audit_by_action = {row["action"]: int(row["n"]) for row in audit_result.mappings().all()}

        links_result = await conn.execute(
            text(
                """
                SELECT count(*) AS n FROM memory_links l
                JOIN memory_notes n ON n.id = l.source_note_id
                WHERE n.user_id = :user_id AND l.invalid_at IS NULL
                """
            ),
            {"user_id": str(user_id)},
        )
        links_count = int(links_result.mappings().first()["n"])

    active = notes_by_status.get("active", 0)
    archived = notes_by_status.get("archived", 0)
    invalidated = notes_by_status.get("invalidated", 0)
    return {
        "notes": {
            "active": active,
            "archived": archived,
            "invalidated": invalidated,
            "total": active + archived + invalidated,
        },
        "audit_last_24h": {
            "add": audit_by_action.get("add", 0),
            "update": audit_by_action.get("update", 0),
            "invalidate": audit_by_action.get("invalidate", 0),
            "read": audit_by_action.get("read", 0),
        },
        "links": links_count,
    }
