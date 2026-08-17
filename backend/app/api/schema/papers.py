"""Pydantic models for the papers/ingestion endpoints (Week 1)."""

from datetime import datetime

from pydantic import BaseModel


class ArxivIngestRequest(BaseModel):
    """POST /api/papers/arxiv request body.

    ``arxiv_id`` accepts a bare id (``"2310.08560"``, optionally
    versioned) or a full arXiv URL (``abs``/``pdf``) -- both are parsed by
    ``app.services.arxiv_service.parse_arxiv_id``.
    """

    arxiv_id: str


class PaperCreateResponse(BaseModel):
    """202 response body shared by both ingestion entry points."""

    id: str
    title: str | None
    status: str


class PaperListItem(BaseModel):
    """A single paper as returned by ``GET /api/papers``."""

    id: str
    title: str | None
    authors: list[str] | None
    arxiv_id: str | None
    status: str
    fail_reason: str | None
    ingested_at: datetime
    chunk_count: int


class PaperListOut(BaseModel):
    """GET /api/papers response body."""

    items: list[PaperListItem]


class PaperStatusOut(BaseModel):
    """GET /api/papers/{id}/status response body."""

    id: str
    status: str
    fail_reason: str | None
    chunk_count: int
