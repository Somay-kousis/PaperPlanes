"""parse_node: converts a fetched PDF into page-aware markdown text.

Delegates to ``app.services.pdf_service.pdf_to_markdown`` (PyMuPDF4LLM),
which also strips the References/Bibliography section. Any parse failure
(corrupt PDF, no extractable text) is treated as a fatal ingestion
failure: ``status`` is set to ``"failed"`` with a ``fail_reason`` rather
than letting the exception propagate, so the graph routes to
``mark_ready`` and the failure is recorded on the ``papers`` row.
"""

from typing import Any

from app.core.graph.state import IngestionState


def parse_node(state: IngestionState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse the fetched PDF into page-aware markdown/plain text."""
    from app.services import pdf_service

    try:
        pages = pdf_service.pdf_to_markdown(state["pdf_bytes"])
    except Exception as exc:
        return {"status": "failed", "fail_reason": f"Failed to parse PDF: {exc}"}

    if not pages or not any(page["text"].strip() for page in pages):
        return {"status": "failed", "fail_reason": "PDF contained no extractable text"}

    return {"pages": pages}
