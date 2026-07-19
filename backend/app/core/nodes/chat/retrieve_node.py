"""retrieve_node: queries papers/chunks AND memory notes for context relevant to the turn.

Embeds the latest human message once, then runs two independent
retrievals against it:

- Paper chunks (existing, top-8 by L2 distance, prefix-filtered on
  ``user_id`` so the CockroachDB vector index on ``(user_id, embedding)``
  can be used).
- Memory notes (``app.memory.retriever.retrieve_and_reinforce``): top-20
  ANN candidates over ACTIVE, temporally-valid notes, rescored by
  recency/importance/relevance, top-5 kept and reinforced.

Each retrieval degrades independently -- a memory-retrieval failure still
lets paper-chunk RAG (and vice versa) proceed, and any failure/absence
falls back to an empty list rather than raising. Degrades entirely to no
retrieval whenever AWS/DB aren't usable or the user has no message text;
``agent_node`` then answers from the model alone (or echo) and the route
surfaces that via ``meta.rag``.
"""

import asyncio
import logging
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.graph.state import ChatState
from app.core.nodes.chat.utils import last_human_text
from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.vectorstore import normalize_embedding

logger = logging.getLogger(__name__)

TOP_K = 8


async def retrieve_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retrieve the top-K most relevant paper chunks and memory notes for the current turn."""
    settings = get_settings()
    empty: dict[str, Any] = {"retrieved_chunks": [], "rag": False, "retrieved_memories": []}
    if not settings.has_aws_credentials:
        return empty

    query_text = last_human_text(state.get("messages", []))
    if not query_text.strip():
        return empty

    user_id = state.get("user_id")
    if not user_id:
        return empty

    chunks: list[dict[str, Any]] = []
    try:
        chunks = await _search_chunks(user_id, query_text)
    except Exception:
        logger.warning("Chunk retrieval failed; answering without paper RAG context", exc_info=True)

    memories: list[dict[str, Any]] = []
    try:
        from app.memory.retriever import retrieve_and_reinforce

        memories = await retrieve_and_reinforce(user_id, query_text)
    except Exception:
        logger.warning("Memory retrieval failed; continuing without memory context", exc_info=True)

    return {
        "retrieved_chunks": chunks,
        "rag": bool(chunks),
        "retrieved_memories": memories,
    }


async def _search_chunks(user_id: str, query_text: str) -> list[dict[str, Any]]:
    from app.core.models.llm import get_embeddings
    from app.memory.db.engine import get_engine

    embeddings = get_embeddings()
    raw_vector = await asyncio.to_thread(embeddings.embed_query, query_text)
    query_vector = normalize_embedding(raw_vector)
    query_literal = format_vector_literal(query_vector)

    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT c.id AS chunk_id, c.paper_id, c.page_number, c.text,
                       p.title AS paper_title
                FROM chunks c
                JOIN papers p ON p.id = c.paper_id
                WHERE c.user_id = :user_id
                ORDER BY c.embedding <-> CAST(:query_vector AS VECTOR)
                LIMIT :top_k
                """
            ),
            {"user_id": str(user_id), "query_vector": query_literal, "top_k": TOP_K},
        )
        rows = result.mappings().all()

    return [
        {
            "chunk_id": str(row["chunk_id"]),
            "paper_id": str(row["paper_id"]),
            "page_number": row["page_number"],
            "text": row["text"],
            "paper_title": row["paper_title"],
        }
        for row in rows
    ]
