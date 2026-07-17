"""``claims`` persistence (Week 3 knowledge graph), bi-temporal like ``notes_repo``.

Mirrors ``app.memory.db.notes_repo``'s style: each function opens (and
commits) its own short transaction, mutations go through
``run_transaction_async`` for 40001 (serialization-failure) retries, and
callers are expected to pass an already-normalized embedding
(``app.memory.db.vectorstore.normalize_embedding``).

Claim lifecycle used by the ingestion pipeline:

- ``active`` -- default, freshly extracted.
- ``disputed`` -- a cross-paper contradiction was found against another
  active claim; BOTH claims are flagged this way, neither is retracted
  (see ``app.core.nodes.ingestion.contradiction_check_node`` --
  ``mark_disputed``, not ``invalidate_claim``, is used here).
- ``invalidated`` -- reserved for when the *same* source later supersedes
  its own earlier claim; stamps ``invalid_at``/``expired_at`` exactly
  like ``notes_repo.invalidate_note``.

``search_similar_active_claims`` only ever returns ``status = 'active'``
rows, so a disputed/invalidated claim naturally drops out of future
contradiction-candidate searches.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async

_CLAIM_FIELDS = """
    id, user_id, paper_id, subject_entity_id, predicate, object_entity_id,
    object_value, statement, source_chunk_id, confidence, status,
    valid_at, invalid_at, created_at, expired_at
"""


def _row_to_claim(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "paper_id": str(row["paper_id"]),
        "subject_entity_id": str(row["subject_entity_id"]) if row["subject_entity_id"] else None,
        "predicate": row["predicate"],
        "object_entity_id": str(row["object_entity_id"]) if row["object_entity_id"] else None,
        "object_value": row["object_value"],
        "statement": row["statement"],
        "source_chunk_id": str(row["source_chunk_id"]) if row["source_chunk_id"] else None,
        "confidence": float(row["confidence"]),
        "status": row["status"],
        "valid_at": row["valid_at"],
        "invalid_at": row["invalid_at"],
        "created_at": row["created_at"],
        "expired_at": row["expired_at"],
    }


async def insert_claim(
    *,
    user_id: uuid.UUID | str,
    paper_id: uuid.UUID | str,
    predicate: str,
    statement: str,
    embedding: list[float],
    subject_entity_id: uuid.UUID | str | None = None,
    object_entity_id: uuid.UUID | str | None = None,
    object_value: str | None = None,
    source_chunk_id: uuid.UUID | str | None = None,
    confidence: float = 0.7,
    status: str = "active",
) -> dict[str, Any]:
    """Insert a new ``claims`` row, returning it as a plain dict."""
    engine = get_engine()
    claim_id = uuid.uuid4()
    params = {
        "id": str(claim_id),
        "user_id": str(user_id),
        "paper_id": str(paper_id),
        "subject_entity_id": str(subject_entity_id) if subject_entity_id else None,
        "predicate": predicate,
        "object_entity_id": str(object_entity_id) if object_entity_id else None,
        "object_value": object_value,
        "statement": statement,
        "source_chunk_id": str(source_chunk_id) if source_chunk_id else None,
        "embedding": format_vector_literal(embedding),
        "confidence": confidence,
        "status": status,
    }

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    INSERT INTO claims
                        (id, user_id, paper_id, subject_entity_id, predicate,
                         object_entity_id, object_value, statement, source_chunk_id,
                         embedding, confidence, status)
                    VALUES
                        (:id, :user_id, :paper_id, CAST(:subject_entity_id AS UUID), :predicate,
                         CAST(:object_entity_id AS UUID), :object_value, :statement,
                         CAST(:source_chunk_id AS UUID), CAST(:embedding AS VECTOR),
                         :confidence, :status)
                    RETURNING {_CLAIM_FIELDS}
                    """
                ),
                params,
            )
            row = result.mappings().first()
        return _row_to_claim(row)

    return await run_transaction_async(_do)


async def get_claim(claim_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Fetch a single claim by id, or ``None`` if it doesn't exist."""
    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT {_CLAIM_FIELDS} FROM claims WHERE id = :id"), {"id": str(claim_id)}
        )
        row = result.mappings().first()
    return _row_to_claim(row) if row is not None else None


async def invalidate_claim(claim_id: uuid.UUID | str) -> None:
    """Mark a claim ``invalidated`` (superseded by its own source), stamping timestamps."""
    engine = get_engine()

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE claims SET status = 'invalidated', invalid_at = now(), "
                    "expired_at = now() WHERE id = :id"
                ),
                {"id": str(claim_id)},
            )

    await run_transaction_async(_do)


async def mark_disputed(claim_id: uuid.UUID | str) -> None:
    """Flag a claim ``disputed`` -- a cross-paper contradiction was found.

    Unlike ``invalidate_claim``, this does NOT stamp ``invalid_at``/
    ``expired_at``: the claim still stands (it may well be true), it's
    just flagged as being in tension with another paper's claim.
    """
    engine = get_engine()

    async def _do() -> None:
        async with engine.engine.begin() as conn:
            await conn.execute(
                text("UPDATE claims SET status = 'disputed' WHERE id = :id"),
                {"id": str(claim_id)},
            )

    await run_transaction_async(_do)


async def search_similar_active_claims(
    user_id: uuid.UUID | str,
    query_embedding: list[float],
    *,
    subject_entity_id: uuid.UUID | str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """ANN search over ACTIVE claims for ``user_id``, preferring a shared subject.

    The SQL is a pure ``ORDER BY embedding <-> ? LIMIT ?`` over the
    ``user_id`` + ``status = 'active'`` prefix, so it's served by the
    ``(user_id, status, embedding)`` C-SPANN vector index rather than a full
    scan. (A two-level ``ORDER BY CASE ..., embedding <-> ?`` -- the previous
    "shared subject first" form -- cannot use the vector index at all, because
    the leading sort key isn't the vector distance, forcing a full-table scan.)

    The "prefer a shared subject" behaviour is preserved app-side instead: we
    over-fetch the nearest candidates by vector distance and then stable-sort
    same-subject claims ahead of the rest (distance order preserved within each
    group) before truncating to ``limit``. Each returned dict carries a
    ``"distance"`` key -- see ``app.memory.scoring.l2_distance_to_cosine_similarity``.
    """
    engine = get_engine()
    query_literal = format_vector_literal(query_embedding)
    # Over-fetch by pure vector distance so the app-side subject re-rank has a
    # window to promote same-subject claims from, without giving up index use.
    fetch_limit = max(limit * 4, 20)
    params = {
        "user_id": str(user_id),
        "query_vector": query_literal,
        "limit": fetch_limit,
    }
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"""
                SELECT {_CLAIM_FIELDS},
                       embedding <-> CAST(:query_vector AS VECTOR) AS distance
                FROM claims
                WHERE user_id = :user_id AND status = 'active'
                ORDER BY embedding <-> CAST(:query_vector AS VECTOR)
                LIMIT :limit
                """
            ),
            params,
        )
        rows = result.mappings().all()

    claims = []
    for row in rows:
        claim = _row_to_claim(row)
        claim["distance"] = float(row["distance"])
        claims.append(claim)

    if subject_entity_id is not None:
        sid = str(subject_entity_id)
        # Stable sort keeps the distance ordering within each group.
        claims.sort(key=lambda c: 0 if c.get("subject_entity_id") == sid else 1)
    return claims[:limit]


async def list_claims(
    user_id: uuid.UUID | str,
    *,
    paper_id: uuid.UUID | str | None = None,
    status: str | None = "active",
    as_of: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List claims for ``user_id``, mirroring ``notes_repo.list_notes``'s ``as_of`` semantics.

    If ``as_of`` is given, reconstructs transaction-time state as of that
    instant and ``status`` is ignored; otherwise filters by ``status``
    (``None``/``"all"`` means no status filter), newest first.
    """
    engine = get_engine()
    clauses = ["user_id = :user_id"]
    params: dict[str, Any] = {"user_id": str(user_id), "limit": limit}

    if paper_id is not None:
        clauses.append("paper_id = :paper_id")
        params["paper_id"] = str(paper_id)

    if as_of is not None:
        clauses.append("created_at <= :as_of AND (expired_at IS NULL OR expired_at > :as_of)")
        params["as_of"] = as_of
    elif status and status != "all":
        clauses.append("status = :status")
        params["status"] = status

    where = " AND ".join(clauses)
    order_by = "valid_at DESC" if as_of is not None else "created_at DESC"

    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT {_CLAIM_FIELDS} FROM claims "
                f"WHERE {where} ORDER BY {order_by} LIMIT :limit"
            ),
            params,
        )
        rows = result.mappings().all()
    return [_row_to_claim(row) for row in rows]
