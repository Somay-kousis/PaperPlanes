"""extract_entities_node: identifies named entities (authors, methods, datasets, etc).

Runs the fast Bedrock model (``get_fast_model()``, Nova Lite) with
structured output against the ``entity_extraction.md`` prompt over each
of the paper's persisted chunks (capped at ``MAX_CHUNKS_FOR_EXTRACTION``),
deduplicates entity mentions within this paper, then resolves each
against the user's existing entity graph via
``app.memory.db.entities_repo.upsert_entity`` (cosine-similarity dedup +
alias tracking).

Also flips ``papers.status`` to ``"extracting"`` at the start so
``GET /api/papers/{id}/status`` reflects progress while this step runs.

Self-degrades like every other ingestion step: no AWS credentials, no
persisted chunks, or any per-chunk/per-entity failure is logged and
skipped rather than raised -- a paper with zero extractable entities
still reaches ``mark_ready``.

NOTE: ``store_chunks_node`` (owned by a different workstream this week)
does not thread persisted chunk ids back into ``state["chunks"]``, so
this node fetches ``(id, chunk_index, page_number, text)`` straight from
``chunks`` for the paper and merges ``id`` onto the chunk dicts already in
``state`` by ``chunk_index`` -- ``extract_claims_node`` downstream reuses
this enriched ``state["chunks"]`` (with ids) as its own chunk source, no
second query needed.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.graph.state import IngestionState

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "entity_extraction.md"

MAX_CHUNKS_FOR_EXTRACTION = 40
ENTITY_TYPES = {"paper", "author", "concept", "method", "dataset", "metric"}
_FALLBACK_ACTOR_STATUS = "extracting"


@lru_cache
def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text()


class ExtractedEntity(BaseModel):
    """A single entity mention, as extracted by the fast model from one chunk."""

    name: str = ""
    type: str = ""
    aliases: list[str] = Field(default_factory=list)


class ExtractedEntities(BaseModel):
    """Structured-output container: entities extracted from one chunk."""

    entities: list[ExtractedEntity] = Field(default_factory=list)


async def _fetch_persisted_chunks(paper_id: str, limit: int) -> list[dict[str, Any]]:
    """Fetch persisted ``(id, chunk_index, page_number, text)`` rows for a paper."""
    from app.memory.db.engine import get_engine

    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, chunk_index, page_number, text FROM chunks "
                "WHERE paper_id = :paper_id ORDER BY chunk_index LIMIT :limit"
            ),
            {"paper_id": str(paper_id), "limit": limit},
        )
        rows = result.mappings().all()
    return [
        {
            "id": str(row["id"]),
            "chunk_index": row["chunk_index"],
            "page_number": row["page_number"],
            "text": row["text"],
        }
        for row in rows
    ]


def _merge_chunk_ids(
    state_chunks: list[dict[str, Any]], persisted: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge persisted chunk ``id``s onto the in-state chunk dicts by ``chunk_index``."""
    if not state_chunks:
        return [
            {"id": row["id"], "chunk_index": row["chunk_index"], "page_number": row["page_number"],
             "text": row["text"]}
            for row in persisted
        ]
    id_by_index = {row["chunk_index"]: row["id"] for row in persisted}
    return [{**chunk, "id": id_by_index.get(chunk.get("chunk_index"))} for chunk in state_chunks]


async def _extract_from_chunk(model: Any, chunk_text: str) -> list[ExtractedEntity]:
    structured = model.with_structured_output(ExtractedEntities)
    prompt = _load_prompt_template().format(chunk_text=chunk_text)
    result = await asyncio.to_thread(structured.invoke, prompt)
    if not isinstance(result, ExtractedEntities):
        result = ExtractedEntities.model_validate(result)
    return result.entities


async def _embed_name(name: str) -> list[float]:
    from app.core.models.llm import get_embeddings
    from app.memory.db.vectorstore import normalize_embedding

    embeddings = get_embeddings()
    raw = await asyncio.to_thread(embeddings.embed_query, name)
    return normalize_embedding(raw)


async def extract_entities_node(
    state: IngestionState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Extract and resolve named entities mentioned in the paper's chunks."""
    if state.get("status") == "failed":
        return {}

    paper_id = state["paper_id"]
    user_id = state["user_id"]

    from app.memory.db import papers_repo

    await papers_repo.update_paper_status(paper_id, _FALLBACK_ACTOR_STATUS)

    persisted_chunks = await _fetch_persisted_chunks(paper_id, MAX_CHUNKS_FOR_EXTRACTION)
    merged_chunks = _merge_chunk_ids(state.get("chunks", []), persisted_chunks)

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.has_aws_credentials or not persisted_chunks:
        logger.info(
            "Skipping entity extraction for paper %s (no AWS credentials or no chunks)", paper_id
        )
        return {"chunks": merged_chunks, "entities": []}

    from app.core.models.llm import get_fast_model
    from app.memory.db import entities_repo

    model = get_fast_model()

    # (name.lower(), type) -> raw names/aliases seen for this mention-key in this paper.
    seen: dict[tuple[str, str], list[str]] = {}
    for chunk in persisted_chunks:
        try:
            extracted = await _extract_from_chunk(model, chunk["text"])
        except Exception:
            logger.warning(
                "Entity extraction failed for chunk %s of paper %s",
                chunk.get("id"),
                paper_id,
                exc_info=True,
            )
            continue

        for entity in extracted:
            name = (entity.name or "").strip()
            etype = (entity.type or "").strip().lower()
            if not name or etype not in ENTITY_TYPES:
                continue
            key = (name.lower(), etype)
            names = seen.setdefault(key, [name])
            for alias in entity.aliases:
                alias = (alias or "").strip()
                if alias and alias not in names:
                    names.append(alias)

    resolved_entities: list[dict[str, Any]] = []
    for (_, etype), raw_names in seen.items():
        canonical_candidate = raw_names[0]
        try:
            embedding = await _embed_name(canonical_candidate)
            resolved = await entities_repo.upsert_entity(
                user_id=user_id, type=etype, name=canonical_candidate, embedding=embedding
            )
        except Exception:
            logger.warning(
                "Failed to resolve entity %r (%s) for paper %s",
                canonical_candidate,
                etype,
                paper_id,
                exc_info=True,
            )
            continue
        resolved_entities.append({**resolved, "raw_names": [n.lower() for n in raw_names]})

    return {"chunks": merged_chunks, "entities": resolved_entities}
