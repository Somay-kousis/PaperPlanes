"""FastAPI application factory and lifespan wiring.

Boots even without a reachable database or AWS credentials: the lifespan
attempts to set up the CockroachDB engine and LangGraph checkpointer, but
degrades gracefully (logs a warning, continues serving) if either fails --
routes that need persistence detect this at request time (see
``app.api.routes.chat``) and fall back accordingly.
"""

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.deps import require_api_token
from app.api.routes import chat, contradictions, health, memory, papers, reflections
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_var
from app.memory.db.checkpointer import close_checkpointer, setup_checkpointer
from app.memory.db.engine import dispose_engine, ping
from app.workers.scheduler import start_scheduler, stop_scheduler

configure_logging()
logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns each request a request id and logs one line on completion.

    The request id is taken from an incoming ``X-Request-ID`` header when
    present, otherwise a uuid4 is generated. It's bound to
    ``request_id_var`` for the lifetime of the request -- so every log line
    emitted while handling it (by this middleware or any route/service code)
    carries the same ``request_id`` -- and echoed back on the response so
    clients/proxies can correlate their own logs with ours.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize DB engine + checkpointer on startup; clean up on shutdown."""
    startup_start = time.perf_counter()
    db_ok = await ping()
    if db_ok:
        try:
            await setup_checkpointer()
            logger.info(
                "Checkpointer initialized; chat persistence is enabled.",
                extra={"db_ok": True, "checkpointer_ok": True},
            )
        except Exception:
            logger.warning(
                "Checkpointer setup failed; chat will run without persistence.",
                extra={"db_ok": True, "checkpointer_ok": False},
                exc_info=True,
            )
        # The reflection scheduler needs a reachable DB; only start it when one
        # is present. start_scheduler() is itself a no-op when disabled via
        # REFLECTION_INTERVAL_SECONDS<=0, and its ticks degrade on failure.
        try:
            start_scheduler()
        except Exception:
            logger.warning(
                "Reflection scheduler failed to start.",
                extra={"db_ok": True, "scheduler_ok": False},
                exc_info=True,
            )
    else:
        logger.warning(
            "Database unreachable at startup; running in degraded mode "
            "(echo chat works, but without persisted history or scheduled reflection).",
            extra={"db_ok": False},
        )

    startup_duration_ms = round((time.perf_counter() - startup_start) * 1000, 2)
    logger.info(
        "startup complete",
        extra={"db_ok": db_ok, "duration_ms": startup_duration_ms},
    )

    yield

    logger.info("shutdown initiated")
    stop_scheduler()
    await close_checkpointer()
    await dispose_engine()
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="PaperPlanes API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENV == "dev" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Added after CORS so it ends up outermost (Starlette treats the
    # most-recently-added middleware as closest to the client): every
    # request gets a request id before anything else runs, and the id is
    # still available while CORS/error handling produce the response.
    app.add_middleware(RequestContextMiddleware)

    # Health/readiness stay open (probes + load balancers). Every data route is
    # gated by the API token when APP_API_TOKEN is configured (no-op otherwise).
    app.include_router(health.router, prefix="/api")
    gated = [Depends(require_api_token)]
    app.include_router(chat.router, prefix="/api", dependencies=gated)
    app.include_router(papers.router, prefix="/api", dependencies=gated)
    app.include_router(memory.router, prefix="/api", dependencies=gated)
    app.include_router(reflections.router, prefix="/api", dependencies=gated)
    app.include_router(contradictions.router, prefix="/api", dependencies=gated)

    return app


app = create_app()
