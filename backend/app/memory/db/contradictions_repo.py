"""``contradictions`` persistence (Week 3 knowledge graph).

Every row links two ``claims`` -- normally from different papers, flagged
by ``app.core.nodes.ingestion.contradiction_check_node`` after
``app.memory.contradiction.judge`` returns a ``"contradicts"`` verdict.
Resolution is a human/agent action recorded via ``resolve_contradiction``
-- it never deletes the row or un-disputes the underlying claims, it just
appends a note explaining how the disagreement was settled.
"""

import uuid
from typing import Any

from sqlalchemy import text

from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async

_CONTRADICTION_FIELDS = (
    "id, claim_a_id, claim_b_id, rationale, detected_at, resolved, resolution_note"
)


def _row_to_contradiction(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "claim_a_id": str(row["claim_a_id"]),
        "claim_b_id": str(row["claim_b_id"]),
        "rationale": row["rationale"],
        "detected_at": row["detected_at"],
        "resolved": bool(row["resolved"]),
        "resolution_note": row["resolution_note"],
    }


async def insert_contradiction(
    claim_a_id: uuid.UUID | str, claim_b_id: uuid.UUID | str, rationale: str
) -> dict[str, Any]:
    """Insert a contradiction for this claim pair, or return the existing one.

    Idempotent on the (unordered) claim pair: if a ``contradictions`` row already
    links these two claims (in either direction), that row is returned instead of
    inserting a duplicate -- so re-ingesting a paper, or a re-run of the
    contradiction pass, doesn't surface the same conflict twice in the UI. The
    check-then-insert runs inside one SERIALIZABLE transaction, so two concurrent
    inserts of the same pair can't both slip through: the loser's read conflicts
    with the winner's write, it retries, and on retry it sees the existing row.
    """
    engine = get_engine()
    params = {
        "id": str(uuid.uuid4()),
        "claim_a_id": str(claim_a_id),
        "claim_b_id": str(claim_b_id),
        "rationale": rationale,
    }

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            existing = await conn.execute(
                text(
                    f"""
                    SELECT {_CONTRADICTION_FIELDS} FROM contradictions
                    WHERE (claim_a_id = :claim_a_id AND claim_b_id = :claim_b_id)
                       OR (claim_a_id = :claim_b_id AND claim_b_id = :claim_a_id)
                    LIMIT 1
                    """
                ),
                params,
            )
            existing_row = existing.mappings().first()
            if existing_row is not None:
                return _row_to_contradiction(existing_row)

            result = await conn.execute(
                text(
                    f"""
                    INSERT INTO contradictions (id, claim_a_id, claim_b_id, rationale)
                    VALUES (:id, :claim_a_id, :claim_b_id, :rationale)
                    RETURNING {_CONTRADICTION_FIELDS}
                    """
                ),
                params,
            )
            row = result.mappings().first()
        return _row_to_contradiction(row)

    return await run_transaction_async(_do)


async def list_contradictions(
    *, resolved: bool | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """List contradictions newest-first, each joined with both claims' paper titles.

    Returns dicts already shaped for
    ``app.api.schema.contradictions.ContradictionOut``:
    ``{id, rationale, detected_at, resolved, resolution_note,
    claim_a: {id, statement, paper_id, paper_title, predicate},
    claim_b: {...}}``.
    """
    engine = get_engine()
    clauses = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit}
    if resolved is not None:
        clauses.append("c.resolved = :resolved")
        params["resolved"] = resolved
    where = " AND ".join(clauses)

    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                f"""
                SELECT c.id, c.rationale, c.detected_at, c.resolved, c.resolution_note,
                       ca.id AS claim_a_id, ca.statement AS claim_a_statement,
                       ca.predicate AS claim_a_predicate, ca.paper_id AS claim_a_paper_id,
                       pa.title AS claim_a_paper_title,
                       cb.id AS claim_b_id, cb.statement AS claim_b_statement,
                       cb.predicate AS claim_b_predicate, cb.paper_id AS claim_b_paper_id,
                       pb.title AS claim_b_paper_title
                FROM contradictions c
                JOIN claims ca ON ca.id = c.claim_a_id
                JOIN claims cb ON cb.id = c.claim_b_id
                JOIN papers pa ON pa.id = ca.paper_id
                JOIN papers pb ON pb.id = cb.paper_id
                WHERE {where}
                ORDER BY c.detected_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        rows = result.mappings().all()

    items = []
    for row in rows:
        items.append(
            {
                "id": str(row["id"]),
                "rationale": row["rationale"],
                "detected_at": row["detected_at"],
                "resolved": bool(row["resolved"]),
                "resolution_note": row["resolution_note"],
                "claim_a": {
                    "id": str(row["claim_a_id"]),
                    "statement": row["claim_a_statement"],
                    "paper_id": str(row["claim_a_paper_id"]),
                    "paper_title": row["claim_a_paper_title"],
                    "predicate": row["claim_a_predicate"],
                },
                "claim_b": {
                    "id": str(row["claim_b_id"]),
                    "statement": row["claim_b_statement"],
                    "paper_id": str(row["claim_b_paper_id"]),
                    "paper_title": row["claim_b_paper_title"],
                    "predicate": row["claim_b_predicate"],
                },
            }
        )
    return items


async def resolve_contradiction(
    contradiction_id: uuid.UUID | str, resolution_note: str | None
) -> dict[str, Any] | None:
    """Mark a contradiction resolved, returning the updated row (or ``None`` if unknown)."""
    engine = get_engine()

    async def _do() -> Any:
        async with engine.engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    UPDATE contradictions SET resolved = true, resolution_note = :resolution_note
                    WHERE id = :id
                    RETURNING {_CONTRADICTION_FIELDS}
                    """
                ),
                {"id": str(contradiction_id), "resolution_note": resolution_note},
            )
            return result.mappings().first()

    row = await run_transaction_async(_do)
    return _row_to_contradiction(row) if row is not None else None
