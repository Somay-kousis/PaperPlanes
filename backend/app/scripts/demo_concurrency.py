"""Demonstrate the lost-update anomaly a flat file suffers -- and CockroachDB doesn't.

Runs the same workload two ways and prints the result side by side:

1. **Flat-file analog** -- an in-memory dict updated by N concurrent async tasks,
   each doing read -> (yield) -> write. Because the tasks interleave at the
   ``await``, increments are lost: the final value is < N. This is exactly what a
   JSON file or naive key-value store does under concurrency.

2. **CockroachDB** -- the same N concurrent increments, each as a SERIALIZABLE
   transaction on one ``memory_notes`` row (via ``run_transaction_async``, the
   same retry wrapper every real write path uses). Conflicting transactions abort
   with SQLSTATE 40001 and are retried; no update is lost, so the final value is
   exactly N.

The point of the demo: swapping CockroachDB for a flat file is not a
behaviour-preserving change -- it silently corrupts data the moment two writers
touch the same record. Run (from ``backend/``, against the running DB):

    .venv/bin/python -m app.scripts.demo_concurrency --workers 25
"""

import argparse
import asyncio
import logging
import uuid

from sqlalchemy import text

from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async

logging.basicConfig(level=logging.WARNING)

# Reuse the isolated benchmark user so this never touches demo-user data.
BENCH_USER_ID = "00000000-0000-0000-0000-0000000b3c40"
BENCH_EMAIL = "scale-bench@paperplanes.local"
_CONFLICT_WINDOW_S = 0.01  # widen the read->write gap so conflicts actually happen


class _RetryCounter(logging.Handler):
    """Counts ``run_transaction_async`` retry warnings emitted during the demo."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "Retrying async transaction" in record.getMessage():
            self.count += 1


async def dict_demo(workers: int) -> int:
    """The flat-file analog: concurrent read->yield->write on an in-memory dict."""
    store = {"count": 0}

    async def worker() -> None:
        current = store["count"]
        await asyncio.sleep(_CONFLICT_WINDOW_S)  # yield: another task interleaves here
        store["count"] = current + 1

    await asyncio.gather(*(worker() for _ in range(workers)))
    return store["count"]


async def crdb_demo(workers: int) -> tuple[int, int]:
    """N concurrent SERIALIZABLE increments on one row; returns (final_count, retries)."""
    engine = get_engine()
    note_id = str(uuid.uuid4())
    zero_vec = format_vector_literal([0.0] * 1024)

    async with engine.engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (id, email) VALUES (:id, :email) ON CONFLICT (id) DO NOTHING"),
            {"id": BENCH_USER_ID, "email": BENCH_EMAIL},
        )
        await conn.execute(
            text(
                "INSERT INTO memory_notes (id, user_id, content, embedding, access_count, status) "
                "VALUES (:id, :uid, :content, CAST(:emb AS VECTOR), 0, 'active')"
            ),
            {
                "id": note_id,
                "uid": BENCH_USER_ID,
                "content": "concurrency demo counter",
                "emb": zero_vec,
            },
        )

    counter = _RetryCounter()
    retry_logger = logging.getLogger("app.memory.db.retry")
    retry_logger.addHandler(counter)
    retry_logger.setLevel(logging.WARNING)

    async def worker() -> None:
        async def _do() -> None:
            async with engine.engine.begin() as conn:
                current = (
                    await conn.execute(
                        text("SELECT access_count FROM memory_notes WHERE id = :id"),
                        {"id": note_id},
                    )
                ).scalar()
                await asyncio.sleep(_CONFLICT_WINDOW_S)  # widen the conflict window
                await conn.execute(
                    text("UPDATE memory_notes SET access_count = :v WHERE id = :id"),
                    {"v": current + 1, "id": note_id},
                )

        await run_transaction_async(_do, max_attempts=50)

    try:
        await asyncio.gather(*(worker() for _ in range(workers)))
        async with engine.engine.connect() as conn:
            final = (
                await conn.execute(
                    text("SELECT access_count FROM memory_notes WHERE id = :id"), {"id": note_id}
                )
            ).scalar()
    finally:
        retry_logger.removeHandler(counter)
        async with engine.engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM memory_notes WHERE id = :id"), {"id": note_id}
            )

    return int(final), counter.count


async def main(workers: int) -> None:
    dict_final = await dict_demo(workers)
    crdb_final, retries = await crdb_demo(workers)

    print(f"\n{workers} concurrent writers incrementing one counter:\n")
    print(f"  flat-file analog (in-memory dict): final = {dict_final:>3} / {workers}"
          f"   -> {'LOST UPDATES' if dict_final < workers else 'ok'} "
          f"({workers - dict_final} increments silently lost)")
    print(f"  CockroachDB (SERIALIZABLE + retry): final = {crdb_final:>3} / {workers}"
          f"   -> {'CONSISTENT' if crdb_final == workers else 'INCONSISTENT'} "
          f"({retries} serialization conflicts detected and retried)")
    print()
    if dict_final < workers and crdb_final == workers:
        print("A flat file loses writes under concurrency; CockroachDB does not.")


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=25)
    args = parser.parse_args()
    asyncio.run(main(args.workers))


if __name__ == "__main__":
    _cli()
