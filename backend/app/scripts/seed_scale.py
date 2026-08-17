"""Seed the memory store to real scale, to make CockroachDB's vector index load-bearing.

At a handful of notes, an ANN query is indistinguishable from a brute-force
scan -- which is exactly the "you could swap CockroachDB for a dict" critique.
This script bulk-inserts ``--count`` memory notes (default 10k) for a dedicated
benchmark user with unit-normalized random VECTOR(1024) embeddings, so the
C-SPANN vector index actually has a corpus to accelerate over.

Embeddings are random unit vectors generated locally (NOT Bedrock) -- we're
stress-testing the *index*, not embedding quality, so this stays fast and free.
Vectors are L2-normalized to match the app's single normalization choke point
(``app.memory.db.vectorstore.normalize_embedding``), so L2 order == cosine order.

Usage (from ``backend/``, against the running DB):

    .venv/bin/python -m app.scripts.seed_scale --count 10000
    .venv/bin/python -m app.scripts.seed_scale --explain     # just show the plan
    .venv/bin/python -m app.scripts.seed_scale --clear        # remove benchmark notes

The benchmark user is isolated (its own user_id), so this never pollutes the
demo user's memory.
"""

import argparse
import asyncio
import logging
import random
import uuid

from sqlalchemy import text

from app.core.config import get_settings
from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Stable, dedicated benchmark user so scale data never mixes with the demo user.
BENCH_USER_ID = "00000000-0000-0000-0000-0000000b3c40"
BENCH_EMAIL = "scale-bench@paperplanes.local"

_TOPICS = [
    "vector search",
    "bi-temporal memory",
    "contradiction detection",
    "reflection and decay",
    "graph traversal",
    "serializable transactions",
    "agent memory consolidation",
    "retrieval augmented generation",
]


def _unit_vector(dim: int, rng: random.Random) -> list[float]:
    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = sum(c * c for c in vec) ** 0.5 or 1.0
    return [c / norm for c in vec]


async def _ensure_bench_user(conn) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO users (id, email)
            VALUES (:id, :email)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": BENCH_USER_ID, "email": BENCH_EMAIL},
    )


async def seed(count: int, batch_size: int = 500) -> None:
    settings = get_settings()
    dim = settings.EMBED_DIM
    rng = random.Random(1234)
    engine = get_engine()

    async with engine.engine.begin() as conn:
        await _ensure_bench_user(conn)

    inserted = 0
    while inserted < count:
        n = min(batch_size, count - inserted)
        rows = []
        params: dict[str, object] = {}
        for i in range(n):
            topic = _TOPICS[(inserted + i) % len(_TOPICS)]
            vec = format_vector_literal(_unit_vector(dim, rng))
            rows.append(
                f"(:id{i}, :uid, :content{i}, CAST(:emb{i} AS VECTOR), :imp{i}, 'active')"
            )
            params[f"id{i}"] = str(uuid.uuid4())
            params[f"content{i}"] = f"Benchmark note {inserted + i} about {topic}."
            params[f"emb{i}"] = vec
            params[f"imp{i}"] = round(rng.uniform(0.3, 0.9), 3)
        params["uid"] = BENCH_USER_ID
        stmt = (
            "INSERT INTO memory_notes (id, user_id, content, embedding, importance, status) "
            "VALUES " + ", ".join(rows)
        )

        async def _do(stmt: str = stmt, params: dict[str, object] = params) -> None:
            async with engine.engine.begin() as conn:
                await conn.execute(text(stmt), params)

        # Vector-index maintenance makes concurrent batch inserts contend on the
        # cloud cluster (SERIALIZABLE => 40001); retry exactly like every real
        # write path in the app does (app.memory.db.retry).
        await run_transaction_async(_do)
        inserted += n
        logger.info("seeded %d/%d notes", inserted, count)

    logger.info("done: %d benchmark notes for user %s", count, BENCH_USER_ID)


async def clear() -> None:
    engine = get_engine()
    async with engine.engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM memory_notes WHERE user_id = :uid"), {"uid": BENCH_USER_ID}
        )
    logger.info("cleared %s benchmark notes", result.rowcount)


async def explain() -> None:
    settings = get_settings()
    rng = random.Random(999)
    query_vec = format_vector_literal(_unit_vector(settings.EMBED_DIM, rng))
    engine = get_engine()
    # CockroachDB's EXPLAIN does not accept placeholders, so the (constant,
    # trusted) user_id and the query vector are both inlined as literals.
    sql = text(
        f"""
        EXPLAIN ANALYZE
        SELECT id, embedding <-> CAST('{query_vec}' AS VECTOR) AS distance
        FROM memory_notes
        WHERE user_id = '{BENCH_USER_ID}'
          AND status = 'active'
        ORDER BY embedding <-> CAST('{query_vec}' AS VECTOR)
        LIMIT 5
        """
    )
    async with engine.engine.connect() as conn:
        count = (
            await conn.execute(
                text("SELECT count(*) FROM memory_notes WHERE user_id = :uid"),
                {"uid": BENCH_USER_ID},
            )
        ).scalar()
        result = await conn.execute(sql)
        plan = "\n".join(row[0] for row in result.fetchall())
    print(f"\nBenchmark corpus: {count} notes for user {BENCH_USER_ID}\n")
    print(plan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--clear", action="store_true", help="remove benchmark notes and exit")
    parser.add_argument("--explain", action="store_true", help="EXPLAIN ANALYZE the ANN query")
    args = parser.parse_args()

    if args.clear:
        asyncio.run(clear())
        return
    if args.explain:
        asyncio.run(explain())
        return
    asyncio.run(seed(args.count))
    asyncio.run(explain())


if __name__ == "__main__":
    main()
