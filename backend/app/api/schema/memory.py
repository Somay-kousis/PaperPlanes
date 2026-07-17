"""Pydantic models for the memory-inspector & reflection endpoints."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class MemoryNoteOut(BaseModel):
    """A memory note as returned to clients (full row, all four timestamps)."""

    id: str
    user_id: str
    content: str
    keywords: list[str]
    tags: list[str]
    context: str | None
    importance: float
    strength: float
    last_accessed_at: datetime
    access_count: int
    confidence: float
    is_user_stated: bool
    source_episode_id: str | None
    derived_from: list[str]
    status: str
    valid_at: datetime
    invalid_at: datetime | None
    created_at: datetime
    expired_at: datetime | None


class MemoryNotesListOut(BaseModel):
    """GET /api/memory/notes response body."""

    items: list[MemoryNoteOut]


class MemoryNoteSummary(BaseModel):
    """A minimal note summary, used as the "other side" of a link."""

    id: str
    content: str
    status: str


class MemoryLinkOut(BaseModel):
    """A single ``memory_links`` row touching a note, from that note's point of view."""

    id: str
    relation_type: str
    weight: float
    direction: Literal["in", "out"]
    other: MemoryNoteSummary


class MemoryAuditRowOut(BaseModel):
    """A single ``memory_audit_log`` row."""

    id: str
    actor: str
    action: str
    target_table: str
    target_id: str
    reason: str | None
    details: dict[str, Any]
    created_at: datetime


class MemoryNoteDetailOut(MemoryNoteOut):
    """GET /api/memory/notes/{id} response body.

    Flattens the note's own fields to the top level (``content``, timestamps,
    meters, ...) and adds ``links``/``audit`` alongside them, matching what the
    frontend's NoteDetail consumes (``note.content``, ``note.links``, ...).
    """

    links: list[MemoryLinkOut]
    audit: list[MemoryAuditRowOut]


class MemoryAuditListOut(BaseModel):
    """GET /api/memory/audit response body."""

    items: list[MemoryAuditRowOut]


class MemoryNoteStatusCounts(BaseModel):
    """Note counts by status, for GET /api/memory/stats."""

    active: int
    archived: int
    invalidated: int
    total: int


class MemoryAuditActionCounts(BaseModel):
    """Audit-row counts by action over the trailing 24h, for GET /api/memory/stats."""

    add: int
    update: int
    invalidate: int
    read: int


class MemoryStatsOut(BaseModel):
    """GET /api/memory/stats response body."""

    notes: MemoryNoteStatusCounts
    audit_last_24h: MemoryAuditActionCounts
    links: int


class ReflectionOut(BaseModel):
    """A reflection record as returned to clients."""

    id: str
    user_id: str
    content: str
    cites: list[str]
    trigger_reason: str
    importance: float
    created_at: datetime


class ReflectionsListOut(BaseModel):
    """GET /api/reflections response body."""

    items: list[ReflectionOut]


class ReflectionRunOut(BaseModel):
    """POST /api/reflections/run response body: one reflection cycle's counts."""

    reflections_created: int
    notes_archived: int
    contradictions_found: int
