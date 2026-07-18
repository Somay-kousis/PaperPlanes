"""fetch_node: downloads a paper's staged PDF bytes from S3.

The PDF itself is uploaded to S3 by the route handler (``app.api.routes.papers``)
before the ingestion graph is even invoked -- this node just pulls those
bytes back down (from ``state["s3_key"]``) so the rest of the pipeline has
something to parse. Any failure here (missing object, S3 unreachable) is
caught and turned into ``status: "failed"`` rather than raised, so the
graph can route to ``mark_ready`` and record it on the ``papers`` row.
"""

from typing import Any

from app.core.graph.state import IngestionState


async def fetch_node(state: IngestionState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch the paper's staged PDF bytes from S3."""
    from app.services import s3_service

    try:
        pdf_bytes = await s3_service.download_bytes(state["s3_key"])
    except Exception as exc:
        return {"status": "failed", "fail_reason": f"Failed to fetch PDF from storage: {exc}"}

    if not pdf_bytes:
        return {"status": "failed", "fail_reason": "Fetched PDF from storage was empty"}

    return {"pdf_bytes": pdf_bytes}
