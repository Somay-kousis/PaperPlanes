"""Chunk persistence: bulk-insert embedded chunks into CockroachDB.

Uses a raw *synchronous* psycopg connection (run inside a worker thread
via ``asyncio.to_thread``) rather than the async SQLAlchemy engine in
``app.memory.db.engine``, specifically so the batch insert can go through
``app.memory.db.retry.run_transaction`` -- a plain blocking retry loop,
not asyncio-aware. Running the whole thing in a thread keeps the event
loop free while a serialization-conflict retry sleeps.
"""

import asyncio
import uuid
from typing import Any

import psycopg

from app.core.config import get_settings
from app.memory.db.retry import run_transaction


def format_vector_literal(vec: list[float]) -> str:
    """Format an embedding vector as a CockroachDB ``VECTOR`` literal string.

    e.g. ``[0.1, -0.2]`` -> ``"[0.10000000,-0.20000000]"``, suitable for
    interpolation into a query as ``'<literal>'::VECTOR``.
    """
    return "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"


def _insert_rows_sync(dsn: str, rows: list[tuple[Any, ...]]) -> int:
    def _do() -> int:
        with psycopg.connect(dsn, autocommit=False) as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks
                    (id, user_id, paper_id, chunk_index, page_number, text, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::VECTOR)
                """,
                rows,
            )
            conn.commit()
        return len(rows)

    return run_transaction(_do)


async def store_chunks(
    *, user_id: uuid.UUID | str, paper_id: uuid.UUID | str, chunks: list[dict[str, Any]]
) -> int:
    """Batch-insert ``chunks`` (each with an ``embedding`` list) for a paper."""
    if not chunks:
        return 0

    settings = get_settings()
    rows = [
        (
            str(uuid.uuid4()),
            str(user_id),
            str(paper_id),
            chunk["chunk_index"],
            chunk.get("page_number"),
            chunk["text"],
            chunk.get("token_count"),
            format_vector_literal(chunk["embedding"]),
        )
        for chunk in chunks
    ]
    return await asyncio.to_thread(_insert_rows_sync, settings.DATABASE_URL, rows)
