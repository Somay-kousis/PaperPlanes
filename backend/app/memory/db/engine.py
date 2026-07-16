"""CockroachDB async SQLAlchemy engine, shared across the app.

Built on top of ``langchain_cockroachdb.CockroachDBEngine``, which wraps a
plain SQLAlchemy ``AsyncEngine`` with CockroachDB-aware retry helpers
(``init_vectorstore_table`` etc.). We construct the underlying
``AsyncEngine`` ourselves (rather than via
``CockroachDBEngine.from_connection_string``) so we can normalize
whichever DSN scheme ``Settings.DATABASE_URL`` uses (``postgresql://`` or
``cockroachdb://``) onto an explicit, async-capable driver.

This module is intentionally resilient: constructing the engine does not
connect to the database, so importing it and even calling ``get_engine()``
works even if CockroachDB is unreachable. Only actually running a query
(e.g. via ``ping()``) can fail, and callers (health checks, chat routes)
are expected to catch that and degrade gracefully.
"""

import logging
from functools import lru_cache

from langchain_cockroachdb import CockroachDBEngine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def normalize_async_dsn(dsn: str) -> str:
    """Rewrite ``dsn`` onto the async CockroachDB dialect (``cockroachdb+psycopg``).

    Two constraints force the rewrite: SQLAlchemy's ``create_async_engine``
    requires an async-capable driver named in the URL, and the plain
    ``postgresql`` dialect cannot parse CockroachDB's version string
    (``AssertionError: Could not determine version``) — only the
    ``cockroachdb`` dialect from ``sqlalchemy-cockroachdb`` handles it.
    DSNs that already name a driver (contain ``+``) are left untouched.
    """
    if "://" not in dsn:
        return dsn
    scheme, rest = dsn.split("://", 1)
    if "+" in scheme:
        return dsn
    if scheme in ("postgresql", "postgres", "cockroachdb"):
        return f"cockroachdb+psycopg://{rest}"
    return dsn


@lru_cache
def get_engine() -> CockroachDBEngine:
    """Return a process-wide ``CockroachDBEngine`` (lazy singleton).

    Does not eagerly connect; SQLAlchemy async engines are lazy by
    construction. Cached so the app and all requests share one connection
    pool.
    """
    settings = get_settings()
    async_dsn = normalize_async_dsn(settings.DATABASE_URL)
    async_engine = create_async_engine(async_dsn, pool_pre_ping=True)
    return CockroachDBEngine.from_engine(async_engine)


async def ping() -> bool:
    """Run ``SELECT 1`` against the database; return True on success.

    Used by the health/readiness endpoints. Any exception (network error,
    auth failure, DB down) is caught and turned into ``False`` rather than
    propagating, since a down database should degrade the app, not crash
    it.
    """
    try:
        engine = get_engine()
        async with engine.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("Database ping failed", exc_info=True)
        return False


async def dispose_engine() -> None:
    """Dispose of the cached engine's connection pool (app shutdown/tests)."""
    if get_engine.cache_info().currsize == 0:
        return
    engine = get_engine()
    await engine.aclose()
    get_engine.cache_clear()
