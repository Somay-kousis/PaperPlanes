"""Pydantic models for the chat/session endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

DEMO_USER_ID = "demo"


class SessionCreate(BaseModel):
    """POST /api/sessions request body.

    ``user_id`` defaults to the single demo user until real auth lands;
    the frontend currently sends an empty body.
    """

    user_id: str = DEMO_USER_ID
    title: str | None = None


class SessionOut(BaseModel):
    """A session as returned to clients."""

    id: str
    user_id: str
    title: str | None
    created_at: datetime
    last_active_at: datetime


class SessionListOut(BaseModel):
    """GET /api/sessions response body."""

    items: list[SessionOut]


class MessageCreate(BaseModel):
    """POST /api/sessions/{id}/messages request body."""

    user_id: str = DEMO_USER_ID
    content: str


class Citation(BaseModel):
    """A single retrieved paper chunk backing an assistant reply."""

    chunk_id: str
    paper_id: str
    paper_title: str | None = None
    page_number: int | None = None
    snippet: str


class MemoryCitation(BaseModel):
    """A single retrieved memory note backing an assistant reply."""

    note_id: str
    snippet: str
    score: float


class MessageOut(BaseModel):
    """A single chat message (either role) as returned to clients."""

    role: str
    content: str
    created_at: datetime | None = None
    citations: list[Citation] | None = None
    memory_citations: list[MemoryCitation] | None = None


class ChatReplyMeta(BaseModel):
    """Metadata describing how a reply was produced, for observability."""

    degraded: bool = Field(
        default=False,
        description=(
            "True if the checkpointer/DB was unavailable and the graph ran without persistence."
        ),
    )
    used_model: str = Field(default="echo", description="'echo' or the Bedrock model id used.")
    rag: bool = Field(
        default=False,
        description="True if retrieved paper chunks were used to ground this reply.",
    )


class ChatReply(BaseModel):
    """POST /api/sessions/{id}/messages response body."""

    session_id: str
    reply: MessageOut
    meta: ChatReplyMeta
