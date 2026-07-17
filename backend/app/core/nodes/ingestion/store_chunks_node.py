"""store_chunks_node: persists embedded chunks into CockroachDB.

Delegates to ``app.memory.db.chunks_repo.store_chunks``, a batch insert
wrapped in ``app.memory.db.retry.run_transaction`` for 40001
(serialization-failure) retries.
"""

from typing import Any

from app.core.graph.state import IngestionState


async def store_chunks_node(
    state: IngestionState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Persist chunk rows (text + embedding) to the database."""
    if state.get("status") == "failed":
        return {}

    from app.memory.db.chunks_repo import store_chunks

    try:
        await store_chunks(
            user_id=state["user_id"],
            paper_id=state["paper_id"],
            chunks=state.get("chunks", []),
        )
    except Exception as exc:
        return {"status": "failed", "fail_reason": f"Failed to store chunks: {exc}"}

    return {}
