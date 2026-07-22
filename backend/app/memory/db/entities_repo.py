"""``entities``/``entity_aliases`` persistence (Week 3 knowledge graph).

Mirrors ``app.memory.db.notes_repo``'s style: async SQLAlchemy engine,
each function opens (and commits) its own short transaction, mutations go
through ``app.memory.db.retry.run_transaction_async`` for CockroachDB
serialization-failure retries, and every embedding is expected to already
be normalized (``app.memory.db.vectorstore.normalize_embedding``) by the
caller before it reaches here.

``upsert_entity`` is the single entry point for resolving an extracted
entity mention against the user's existing entity graph: an ANN search
over ``entities`` (filtered ``user_id =`` first so the
``(user_id, embedding)`` vector index is used) finds the closest existing
entities; if the closest same-type row clears ``ENTITY_DEDUP_THRESHOLD``,
the mention is folded into that entity (recording ``name`` as a new alias
if it isn't one already) rather than creating a duplicate row for the
same real-world entity extracted with slightly different wording across
papers/chunks.
"""

import uuid
from typing import Any

from sqlalchemy import text

from app.memory import audit
from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async
from app.memory.scoring import l2_distance_to_cosine_similarity

ENTITY_DEDUP_THRESHOLD = 0.82
_DEDUP_SEARCH_LIMIT = 5
_ACTOR = "system:extract_entities"

_ENTITY_FIELDS = "id, user_id, type, canonical_name, metadata, first_seen_at"


def _row_to_entity(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "type": row["type"],
        "canonical_name": row["canonical_name"],
        "metadata": row["metadata"] or {},
        "first_seen_at": row["first_seen_at"],
    }


async def _find_dedup_candidate(
    user_id: uuid.UUID | str, entity_type: str, embedding: list[float]
) -> dict[str, Any] | None:
    """Return the closest existing entity of ``user_id``/``entity_type``, if similar enough.

    Rows come back distance-ordered (closest first). Non-matching-type
    rows are skipped (a closer entity of a different type says nothing
    about whether a same-type match exists); the first same-type row
    that fails the threshold ends the search, since every subsequent row
    is strictly farther away and can only be less similar.
    """
    engine = get_engine()
    query_literal = format_vector_literal(embedding)
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"""
                SELECT {_ENTITY_FIELDS},
                       embedding <-> CAST(:query_vector AS VECTOR) AS distance
                FROM entities
                WHERE user_id = :user_id
                ORDER BY embedding <-> CAST(:query_vector AS VECTOR)
                LIMIT :limit
                """
            ),
            {"user_id": str(user_id), "query_vector": query_literal, "limit": _DEDUP_SEARCH_LIMIT},
        )
        rows = result.mappings().all()

    for row in rows:
        if row["type"] != entity_type:
            continue
        similarity = l2_distance_to_cosine_similarity(float(row["distance"]))
        if similarity >= ENTITY_DEDUP_THRESHOLD:
            return _row_to_entity(row)
        break
    return None


async def _maybe_add_alias(entity_id: uuid.UUID | str, alias: str) -> None:
    """Insert ``alias`` into ``entity_aliases`` if it isn't already recorded."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM entity_aliases WHERE entity_id = :entity_id AND alias = :alias"),
            {"entity_id": str(entity_id), "alias": alias},
        )
        exists = result.first() is not None
    if exists:
        return

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO entity_aliases (id, entity_id, alias) "
                    "VALUES (:id, :entity_id, :alias)"
                ),
                {"id": str(uuid.uuid4()), "entity_id": str(entity_id), "alias": alias},
            )

    await run_transaction_async(_do)


async def upsert_entity(
    *, user_id: uuid.UUID | str, type: str, name: str, embedding: list[float]
) -> dict[str, Any]:
    """Resolve an extracted entity mention, reusing a near-duplicate or creating a new row.

    On reuse: if ``name`` isn't already a known alias of the matched
    entity, it's recorded in ``entity_aliases``. On create: inserts a new
    ``entities`` row and writes an audit ``"add"`` entry (only new
    entities are audited -- reuse is not itself a mutation worth
    recording beyond the alias insert).
    """
    existing = await _find_dedup_candidate(user_id, type, embedding)
    if existing is not None:
        if name.strip() and name.strip() != existing["canonical_name"]:
            await _maybe_add_alias(existing["id"], name.strip())
        return existing

    engine = get_engine()
    entity_id = uuid.uuid4()
    params = {
        "id": str(entity_id),
        "user_id": str(user_id),
        "type": type,
        "canonical_name": name,
        "embedding": format_vector_literal(embedding),
    }

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    INSERT INTO entities (id, user_id, type, canonical_name, embedding)
                    VALUES (:id, :user_id, :type, :canonical_name, CAST(:embedding AS VECTOR))
                    RETURNING {_ENTITY_FIELDS}
                    """
                ),
                params,
            )
            row = result.mappings().first()
        return _row_to_entity(row)

    entity = await run_transaction_async(_do)
    await audit.write_audit(
        None,
        user_id=user_id,
        actor=_ACTOR,
        action="add",
        target_table="entities",
        target_id=entity["id"],
        reason=f"new {type} entity extracted",
        details={"after": entity},
    )
    return entity


async def get_entity(entity_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Fetch a single entity by id, or ``None`` if it doesn't exist."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT {_ENTITY_FIELDS} FROM entities WHERE id = :id"), {"id": str(entity_id)}
        )
        row = result.mappings().first()
    return _row_to_entity(row) if row is not None else None


async def list_entities(
    user_id: uuid.UUID | str, *, type: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """List entities for ``user_id``, optionally filtered by ``type``, newest first."""
    engine = get_engine()
    clauses = ["user_id = :user_id"]
    params: dict[str, Any] = {"user_id": str(user_id), "limit": limit}
    if type is not None:
        clauses.append("type = :type")
        params["type"] = type
    where = " AND ".join(clauses)

    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_ENTITY_FIELDS} FROM entities WHERE {where} "
                "ORDER BY first_seen_at DESC LIMIT :limit"
            ),
            params,
        )
        rows = result.mappings().all()
    return [_row_to_entity(row) for row in rows]
