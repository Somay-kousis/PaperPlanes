"""Pydantic models for the contradictions endpoints (Week 3 knowledge graph)."""

from datetime import datetime

from pydantic import BaseModel


class ClaimRefOut(BaseModel):
    """One side of a contradiction, as returned by ``GET /api/contradictions``."""

    id: str
    statement: str
    paper_id: str
    paper_title: str | None
    predicate: str


class ContradictionOut(BaseModel):
    """A single contradiction, as returned by ``GET /api/contradictions``."""

    id: str
    rationale: str
    detected_at: datetime
    resolved: bool
    resolution_note: str | None
    claim_a: ClaimRefOut
    claim_b: ClaimRefOut


class ContradictionsListOut(BaseModel):
    """GET /api/contradictions response body."""

    items: list[ContradictionOut]


class ResolveContradictionRequest(BaseModel):
    """POST /api/contradictions/{id}/resolve request body."""

    resolution_note: str | None = None


class ResolveContradictionOut(BaseModel):
    """POST /api/contradictions/{id}/resolve response body."""

    id: str
    resolved: bool
    resolution_note: str | None
