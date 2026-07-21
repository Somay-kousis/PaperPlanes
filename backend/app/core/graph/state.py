"""LangGraph state schemas shared by the chat and ingestion graphs."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    """State threaded through the chat graph.

    ``messages`` uses LangGraph's ``add_messages`` reducer so nodes can
    return partial updates (e.g. a single new AIMessage) and have them
    appended to the running conversation instead of overwriting it.
    """

    messages: Annotated[list[Any], add_messages]
    user_id: str
    session_id: str
    retrieved_memories: list[dict[str, Any]]
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    used_model: str
    rag: bool
    token_budget: int
    memory_context_block: str
    memory_citations: list[dict[str, Any]]
    assistant_episode_id: str | None
    fact_candidates: list[dict[str, Any]]
    memory_write_results: list[dict[str, Any]]


class IngestionState(TypedDict, total=False):
    """State threaded through the paper-ingestion graph (Week 1+)."""

    user_id: str
    paper_id: str
    s3_key: str
    pdf_bytes: bytes
    pages: list[dict[str, Any]]
    raw_text: str
    chunks: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    status: str
    fail_reason: str | None
