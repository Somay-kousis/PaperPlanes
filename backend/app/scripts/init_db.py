"""Apply SQL migrations to CockroachDB, then set up the LangGraph checkpointer.

Usage::

    python -m app.scripts.init_db

Applies every ``*.sql`` file in ``app/memory/db/migrations`` in filename
order, tracking applied filenames in a ``schema_migrations`` table so
re-running this script is idempotent (already-applied files are skipped).

``000_settings.sql`` sets a cluster setting that a restricted-privilege
CockroachDB Cloud tenant may not be allowed to change (it may already be
enabled cluster-wide). A failure applying that specific file is logged as
a warning and does NOT stop the script; every other migration failing is
fatal.

Finally, calls ``checkpointer.setup()`` so the ``checkpoints``/
``checkpoint_blobs``/``checkpoint_writes`` tables used by LangGraph exist.
"""

import asyncio
import logging
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.memory.db.checkpointer import close_checkpointer, setup_checkpointer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "memory" / "db" / "migrations"

SETTINGS_MIGRATION_NAME = "000_settings.sql"

CREATE_SCHEMA_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename STRING PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _split_statements(sql_text: str) -> list[str]:
    """Split a migration file's contents into individual statements.

    Full-line ``--`` comments are stripped FIRST, then the remainder is split
    on ``;``. Doing it in this order means a semicolon inside a comment can't
    accidentally cut a statement in half (comment prose routinely contains
    semicolons). This assumes no ``;`` appears inside a string literal in the
    actual SQL, which holds for our migrations.
    """
    lines = [line for line in sql_text.splitlines() if not line.strip().startswith("--")]
    cleaned = "\n".join(lines)
    return [statement.strip() for statement in cleaned.split(";") if statement.strip()]


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)


async def apply_migrations(dsn: str) -> None:
    """Apply every migration file in order, skipping already-applied ones."""
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute(CREATE_SCHEMA_MIGRATIONS_TABLE)
            await cur.execute("SELECT filename FROM schema_migrations")
            applied = {row[0] async for row in cur}

        for path in _migration_files():
            if path.name in applied:
                logger.info("Skipping already-applied migration: %s", path.name)
                continue

            logger.info("Applying migration: %s", path.name)
            sql_text = path.read_text()
            try:
                async with conn.cursor() as cur:
                    for statement in _split_statements(sql_text):
                        await cur.execute(statement)
            except Exception:
                if path.name == SETTINGS_MIGRATION_NAME:
                    logger.warning(
                        "%s failed -- this is expected on CockroachDB Cloud, where "
                        "tenants may not be able to change this cluster setting "
                        "(it is likely already enabled cluster-wide). Continuing.",
                        path.name,
                        exc_info=True,
                    )
                    continue
                logger.error("Migration %s failed", path.name, exc_info=True)
                raise

            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s) "
                    "ON CONFLICT (filename) DO NOTHING",
                    (path.name,),
                )


async def main() -> None:
    settings = get_settings()
    logger.info("Applying migrations against %s", MIGRATIONS_DIR)
    await apply_migrations(settings.DATABASE_URL)

    logger.info("Setting up LangGraph checkpointer tables")
    try:
        await setup_checkpointer()
    finally:
        await close_checkpointer()

    logger.info("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(main())
