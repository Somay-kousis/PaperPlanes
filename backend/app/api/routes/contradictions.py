"""Contradiction inspection/resolution endpoints (Week 3 knowledge graph).

Same convention as ``app.api.routes.memory``: every handler catches DB
errors and turns them into a 503 rather than a raw 500, so a down
database degrades predictably instead of leaking a stack trace.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.schema.contradictions import (
    ContradictionsListOut,
    ResolveContradictionOut,
    ResolveContradictionRequest,
)
from app.memory.db import contradictions_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contradictions", tags=["contradictions"])

_DB_UNAVAILABLE = "Contradiction store is unavailable (database unreachable)."


@router.get("", response_model=ContradictionsListOut)
async def list_contradictions(
    resolved: bool | None = None, limit: int = Query(default=50, ge=1, le=500)
) -> ContradictionsListOut:
    """List contradictions, newest-first, each joined with both claims' paper titles."""
    try:
        rows = await contradictions_repo.list_contradictions(resolved=resolved, limit=limit)
        return ContradictionsListOut(items=rows)
    except Exception as exc:
        logger.warning("DB unavailable listing contradictions", exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc


@router.post("/{contradiction_id}/resolve", response_model=ResolveContradictionOut)
async def resolve_contradiction(
    contradiction_id: str, body: ResolveContradictionRequest
) -> ResolveContradictionOut:
    """Mark a contradiction resolved, recording an optional explanatory note."""
    try:
        row = await contradictions_repo.resolve_contradiction(
            contradiction_id, body.resolution_note
        )
    except Exception as exc:
        logger.warning(
            "DB unavailable resolving contradiction %s", contradiction_id, exc_info=True
        )
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc

    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown contradiction_id: {contradiction_id!r}"
        )

    return ResolveContradictionOut(
        id=row["id"], resolved=row["resolved"], resolution_note=row["resolution_note"]
    )
