"""LangGraph checkpointer wiring for CockroachDB.

``AsyncCockroachDBSaver`` (from ``langchain_cockroachdb``) is exposed by
the library as an async context manager
(``AsyncCockroachDBSaver.from_conn_string(dsn)``) rather than a plain
constructor, because it owns a raw ``psycopg`` connection that must be
closed. To make it usable as a long-lived, app-wide singleton under
FastAPI's lifespan (rather than re-entering a fresh ``async with`` block
per request), this module manually drives that context manager's
``__aenter__``/``__aexit__`` and caches the resulting saver.

Call ``get_checkpointer()`` to obtain the singleton (connects lazily),
``setup_checkpointer()`` once at startup to create/upgrade its tables, and
``close_checkpointer()`` at shutdown.
"""

import logging
from contextlib import AbstractAsyncContextManager
from typing import Any

from langchain_cockroachdb import AsyncCockroachDBSaver

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_saver: AsyncCockroachDBSaver | None = None
_saver_cm: AbstractAsyncContextManager[Any] | None = None


async def get_checkpointer() -> AsyncCockroachDBSaver:
    """Return the process-wide AsyncCockroachDBSaver, connecting if needed.

    Uses ``Settings.DATABASE_URL`` verbatim (plain ``postgresql://`` or
    ``cockroachdb://``, no SQLAlchemy ``+driver`` suffix) -- the saver
    connects via raw psycopg, not SQLAlchemy, and does not understand the
    driver-suffixed DSNs used by ``app.memory.db.engine``.
    """
    global _saver, _saver_cm
    if _saver is not None:
        return _saver

    settings = get_settings()
    _saver_cm = AsyncCockroachDBSaver.from_conn_string(settings.DATABASE_URL)
    _saver = await _saver_cm.__aenter__()
    return _saver


async def setup_checkpointer() -> None:
    """Create/upgrade the checkpointer's tables. Call once at startup.

    Safe to call even when the database is unreachable: the exception is
    logged and re-raised so the caller (app lifespan) can decide whether
    to run in degraded mode.
    """
    checkpointer = await get_checkpointer()
    await checkpointer.setup()


async def close_checkpointer() -> None:
    """Close the underlying connection. Call at app shutdown / in tests."""
    global _saver, _saver_cm
    if _saver_cm is not None:
        await _saver_cm.__aexit__(None, None, None)
    _saver = None
    _saver_cm = None


async def reset_checkpointer() -> None:
    """Drop the cached saver so the next ``get_checkpointer()`` reconnects.

    The saver owns a long-lived psycopg connection that a database
    restart/failover (e.g. a CockroachDB Cloud maintenance window) can drop
    from under us -- after which the cached saver keeps raising ``connection is
    closed``. Calling this clears the cache (best-effort closing the stale
    connection) so a subsequent request reconnects, recovering without an app
    restart. Never raises.
    """
    global _saver, _saver_cm
    cm = _saver_cm
    _saver = None
    _saver_cm = None
    if cm is not None:
        try:
            await cm.__aexit__(None, None, None)
        except Exception:
            logger.warning("Error closing stale checkpointer during reset", exc_info=True)
