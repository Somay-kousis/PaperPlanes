"""Reflection endpoints (Week 3: wired to ``app.memory.reflection``).

Single-user (demo) app, same convention as ``app.api.routes.memory``: every
endpoint operates on the fixed demo user (``ensure_demo_user()``), no
``user_id`` query param needed. Every handler catches DB errors and turns
them into a 503 rather than a raw 500, matching the rest of the API's
degrade-gracefully philosophy.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.schema.memory import ReflectionOut, ReflectionRunOut, ReflectionsListOut
from app.memory.db import reflections_repo
from app.memory.db.users_repo import ensure_demo_user
from app.memory.reflection import run_reflection_cycle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reflections", tags=["reflections"])

_DB_UNAVAILABLE = "Memory store is unavailable (database unreachable)."


@router.get("", response_model=ReflectionsListOut)
async def list_reflections(limit: int = Query(default=50, ge=1, le=500)) -> ReflectionsListOut:
    """List reflections generated for the demo user, newest first."""
    try:
        user_id = await ensure_demo_user()
        rows = await reflections_repo.list_reflections(user_id, limit=limit)
        return ReflectionsListOut(items=[ReflectionOut(**row) for row in rows])
    except Exception as exc:
        logger.warning("DB unavailable listing reflections", exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc


@router.post("/run", response_model=ReflectionRunOut)
async def run_reflection_now() -> ReflectionRunOut:
    """Demo "reflect now" trigger: run one manual reflection cycle for the demo user."""
    try:
        user_id = await ensure_demo_user()
        result = await run_reflection_cycle(user_id, trigger_reason="manual")
        return ReflectionRunOut(**result)
    except Exception as exc:
        logger.warning("DB unavailable running reflection cycle", exc_info=True)
        raise HTTPException(status_code=503, detail=_DB_UNAVAILABLE) from exc
