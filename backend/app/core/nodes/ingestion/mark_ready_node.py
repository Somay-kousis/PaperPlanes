"""mark_ready_node: final ingestion step, flips paper status to 'ready'/'failed'.

Reached either after ``store_chunks`` succeeds, or directly (via the
conditional edges in ``build_ingestion_graph``) the moment any earlier
step set ``state["status"] = "failed"``. Either way, this node is what
actually persists the terminal status onto the ``papers`` row.
"""

from typing import Any

from app.core.graph.state import IngestionState


async def mark_ready_node(
    state: IngestionState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Mark the paper as ready (or failed) at the end of ingestion."""
    from app.memory.db import papers_repo

    if state.get("status") == "failed":
        await papers_repo.update_paper_status(
            state["paper_id"], "failed", fail_reason=state.get("fail_reason")
        )
        return {}

    await papers_repo.update_paper_status(state["paper_id"], "ready")
    return {"status": "ready"}
