"""Background worker entry point that triggers a reflection cycle for the demo user.

Thin wrapper around ``app.memory.reflection.run_reflection_cycle``: resolves
the (single, Week-1-era) demo user and runs one cycle, tagged with
whatever ``trigger_reason`` the caller supplies (``"scheduled"`` from
``app.workers.scheduler``, ``"manual"`` from the
``POST /api/reflections/run`` route -- though that route calls
``run_reflection_cycle`` directly since it already has the demo user id
from ``ensure_demo_user()``). Kept separate from ``app.memory.reflection``
so the scheduler has a single, user-resolution-aware function to call on
its interval without duplicating that resolution logic in every caller.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_reflection_pass(*, trigger_reason: str = "scheduled") -> dict[str, Any]:
    """Run one reflection cycle for the demo user, returning its result counts.

    Never raises: ``run_reflection_cycle`` already degrades internally on
    DB/model failure, and resolving the demo user
    (``ensure_demo_user``) failing (e.g. DB unreachable) is caught here too
    so a scheduled tick never crashes the scheduler loop.
    """
    try:
        from app.memory.db.users_repo import ensure_demo_user
        from app.memory.reflection import run_reflection_cycle

        user_id = await ensure_demo_user()
        return await run_reflection_cycle(user_id, trigger_reason=trigger_reason)
    except Exception:
        logger.warning("Reflection pass failed to run (demo user unresolved?)", exc_info=True)
        return {"reflections_created": 0, "notes_archived": 0, "contradictions_found": 0}
