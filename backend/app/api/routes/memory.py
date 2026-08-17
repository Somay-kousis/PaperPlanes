"""Memory inspection endpoints (Week 2: wired to ``app.memory.db.notes_repo``).

Single-user (demo) app, same convention as ``app.api.routes.papers``: every
endpoint operates on the fixed demo user (``ensure_demo_user()``), no
``user_id`` query param needed. Every handler catches DB errors and turns
them into a 503 rather than a raw 500, so a down database degrades
predictably instead of leaking a stack trace -- consistent with the rest
of the API's degrade-gracefully philosophy.
"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.schema.memory import (
    MemoryAuditListOut,
    MemoryAuditRowOut,
    MemoryNoteDetailOut,
    MemoryNoteOut,
    MemoryNotesListOut,
    MemoryStatsOut,
)
from app.memory.db import notes_repo
from app.memory.db.users_repo import ensure_demo_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

_DB_UNAVAILABLE = "Memory store is unavailable (database unreachable)."


@router.get("/notes", response_model=MemoryNotesListOut)
async def list_notes(
    status: Literal["active", "archived", "invalidated", "all"] = "active",
    as_of: datetime | None = None,
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> MemoryNotesListOut:
    """List memory notes for the demo user.

    ``as_of`` reconstructs transaction-time state ("what did the agent
    believe at time T") and ignores ``status`` entirely; without it,
    notes are filtered by ``status`` (default ``active``), newest first.
    """
    try:
        user_id = await ensure_demo_user()
        rows = await notes_repo.list_notes(user_id, status=status, as_of=as_of, q=q, limit=limit)
        return MemoryNotesListOut(items=[MemoryNoteOut(**row) for row in rows])
    except Exception as exc:
        logger.warning("DB unavailable listing memory notes", exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc


@router.get("/notes/{note_id}", response_model=MemoryNoteDetailOut)
async def get_note(note_id: str) -> MemoryNoteDetailOut:
    """Fetch a single memory note, its links (in/out), and its recent audit history."""
    try:
        note = await notes_repo.get_note(note_id)
    except Exception as exc:
        logger.warning("DB unavailable fetching memory note %s", note_id, exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc

    if note is None:
        raise HTTPException(status_code=404, detail=f"Unknown note_id: {note_id!r}")

    try:
        links = await notes_repo.get_links_for_note(note_id)
        audit_rows = await notes_repo.list_audit(target_id=note_id, limit=20)
    except Exception as exc:
        logger.warning("DB unavailable fetching links/audit for note %s", note_id, exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc

    return MemoryNoteDetailOut(
        **note,
        links=links,
        audit=[MemoryAuditRowOut(**row) for row in audit_rows],
    )


@router.get("/audit", response_model=MemoryAuditListOut)
async def list_audit(
    target_id: str | None = None,
    action: str | None = None,
    since: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> MemoryAuditListOut:
    """List audit-log rows, newest first, optionally filtered by target/action/since."""
    try:
        rows = await notes_repo.list_audit(
            target_id=target_id, action=action, since=since, limit=limit
        )
        return MemoryAuditListOut(items=[MemoryAuditRowOut(**row) for row in rows])
    except Exception as exc:
        logger.warning("DB unavailable listing memory audit log", exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc


@router.get("/stats", response_model=MemoryStatsOut)
async def get_stats() -> MemoryStatsOut:
    """Aggregate note/audit/link counts for the memory-inspector dashboard."""
    try:
        user_id = await ensure_demo_user()
        data = await notes_repo.stats(user_id)
        return MemoryStatsOut(**data)
    except Exception as exc:
        logger.warning("DB unavailable computing memory stats", exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc
