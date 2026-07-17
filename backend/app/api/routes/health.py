"""Health and readiness endpoints.

``/api/healthz`` is a liveness probe: it always returns 200 with a status
body, reporting DB reachability as one of its checks (a down DB does not
fail liveness -- the process is still alive and serving the echo agent).

``/api/readyz`` is a readiness probe: it returns 200 only when the app is
ready to serve fully-persisted traffic (DB reachable), and 503 otherwise,
which is the more appropriate signal for a load balancer / orchestrator
deciding whether to route traffic here.
"""

from fastapi import APIRouter, Response

from app.api.schema.common import HealthStatus, ReadyStatus
from app.memory.db.engine import ping

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthStatus)
async def healthz() -> HealthStatus:
    """Liveness probe: always 200, reports subsystem checks."""
    db_ok = await ping()
    return HealthStatus(status="ok", checks={"db": db_ok})


@router.get("/readyz", response_model=ReadyStatus)
async def readyz(response: Response) -> ReadyStatus:
    """Readiness probe: 200 if DB reachable, 503 (with body) otherwise."""
    db_ok = await ping()
    if not db_ok:
        response.status_code = 503
    return ReadyStatus(ready=db_ok, checks={"db": db_ok})
