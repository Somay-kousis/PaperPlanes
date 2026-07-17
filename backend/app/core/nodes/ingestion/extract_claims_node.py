"""extract_claims_node: extracts subject-predicate-object claims from chunks.

Runs the primary chat model (``get_chat_model()``, Nova Pro) with
structured output against the ``claim_extraction.md`` prompt over each of
the paper's chunks (the same chunks ``extract_entities_node`` fetched and
enriched with persisted chunk ids), resolving ``subject``/``object``
references against the entity map built during entity extraction --
falling back to ``entities_repo.upsert_entity`` for a subject that wasn't
already extracted as an entity (**CRITICAL**: never trust an LLM-returned
id/name blindly -- resolution always goes through the actual candidate
set built from ``state["entities"]``, with upsert as the only path to a
*new* entity id). An object that doesn't match a known entity name/alias
is stored as a scalar ``object_value`` (e.g. ``"92%"``) with
``object_entity_id`` left ``NULL``, per the ``claims`` table's design.

Self-degrades exactly like ``extract_entities_node``: no AWS credentials,
no chunks, or any per-chunk/per-claim failure is logged and skipped
rather than raised -- malformed claims (missing subject/predicate/
statement) are silently skipped.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.graph.state import IngestionState

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "claim_extraction.md"

_FALLBACK_ENTITY_TYPE = "concept"


@lru_cache
def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text()


class ExtractedClaim(BaseModel):
    """A single subject-predicate-object claim, as extracted by the fast model."""

    subject: str = ""
    predicate: str = ""
    object: str = ""
    statement: str = ""
    confidence: float = 0.7


class ExtractedClaims(BaseModel):
    """Structured-output container: claims extracted from one chunk."""

    claims: list[ExtractedClaim] = Field(default_factory=list)


def _build_name_index(entities: list[dict[str, Any]]) -> dict[str, str]:
    """Map every known raw name/alias (lowercased) to its resolved entity id."""
    index: dict[str, str] = {}
    for entity in entities:
        entity_id = entity.get("id")
        if not entity_id:
            continue
        canonical = (entity.get("canonical_name") or "").strip().lower()
        if canonical:
            index.setdefault(canonical, entity_id)
        for raw_name in entity.get("raw_names") or []:
            key = (raw_name or "").strip().lower()
            if key:
                index.setdefault(key, entity_id)
    return index


def _known_entity_names(entities: list[dict[str, Any]]) -> str:
    names = sorted({e["canonical_name"] for e in entities if e.get("canonical_name")})
    return "\n".join(f"- {name}" for name in names) if names else "(none extracted)"


async def _extract_from_chunk(
    model: Any, chunk_text: str, entities_block: str
) -> list[ExtractedClaim]:
    structured = model.with_structured_output(ExtractedClaims)
    prompt = _load_prompt_template().format(entities=entities_block, chunk_text=chunk_text)
    result = await asyncio.to_thread(structured.invoke, prompt)
    if not isinstance(result, ExtractedClaims):
        result = ExtractedClaims.model_validate(result)
    return result.claims


async def _embed_text(value: str) -> list[float]:
    from app.core.models.llm import get_embeddings
    from app.memory.db.vectorstore import normalize_embedding

    embeddings = get_embeddings()
    raw = await asyncio.to_thread(embeddings.embed_query, value)
    return normalize_embedding(raw)


async def _resolve_subject(user_id: str, name_index: dict[str, str], subject: str) -> str | None:
    """Resolve a claim's subject name to an entity id, creating one if needed.

    Subjects are assumed to always name an entity (per the extraction
    prompt); a subject the entity pass never saw falls back to
    ``entities_repo.upsert_entity`` so the claim still gets a subject id
    rather than being dropped. The fallback goes through the same
    dedup-by-embedding path as ``extract_entities_node``, so it can still
    resolve onto an already-known entity rather than duplicating it.
    """
    key = subject.strip().lower()
    if key in name_index:
        return name_index[key]

    from app.memory.db import entities_repo

    embedding = await _embed_text(subject)
    resolved = await entities_repo.upsert_entity(
        user_id=user_id, type=_FALLBACK_ENTITY_TYPE, name=subject.strip(), embedding=embedding
    )
    name_index[key] = resolved["id"]
    return resolved["id"]


async def extract_claims_node(
    state: IngestionState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Extract structured claims (subject/predicate/object) from chunks."""
    if state.get("status") == "failed":
        return {}

    paper_id = state["paper_id"]
    user_id = state["user_id"]
    chunks = state.get("chunks", [])
    if not chunks:
        return {"claims": []}

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.has_aws_credentials:
        logger.info("Skipping claim extraction for paper %s (no AWS credentials)", paper_id)
        return {"claims": []}

    from app.core.models.llm import get_chat_model
    from app.memory.db import claims_repo

    # Claim extraction is the make-or-break input to cross-paper contradiction
    # detection, and the fast model (Nova Lite) proved unreliable here -- it
    # echoed prompt example values and grabbed paper-title meta-claims instead
    # of the substantive quantitative findings. Use the stronger chat model
    # (Nova Pro) for this step; it's per-chunk, not high-volume.
    model = get_chat_model()
    entities = state.get("entities", [])
    name_index = _build_name_index(entities)
    entities_block = _known_entity_names(entities)

    inserted_claims: list[dict[str, Any]] = []
    for chunk in chunks:
        try:
            raw_claims = await _extract_from_chunk(model, chunk["text"], entities_block)
        except Exception:
            logger.warning(
                "Claim extraction failed for chunk %s of paper %s",
                chunk.get("id"),
                paper_id,
                exc_info=True,
            )
            continue

        for raw_claim in raw_claims:
            subject = raw_claim.subject.strip()
            predicate = raw_claim.predicate.strip()
            obj = raw_claim.object.strip()
            statement = raw_claim.statement.strip()
            if not subject or not predicate or not statement:
                logger.debug("Skipping malformed claim (missing required field): %r", raw_claim)
                continue

            try:
                subject_entity_id = await _resolve_subject(user_id, name_index, subject)
                object_entity_id = name_index.get(obj.lower()) if obj else None
                object_value = None if object_entity_id else (obj or None)

                embedding = await _embed_text(statement)
                confidence = max(0.0, min(1.0, raw_claim.confidence))
                claim = await claims_repo.insert_claim(
                    user_id=user_id,
                    paper_id=paper_id,
                    subject_entity_id=subject_entity_id,
                    predicate=predicate,
                    object_entity_id=object_entity_id,
                    object_value=object_value,
                    statement=statement,
                    source_chunk_id=chunk.get("id"),
                    embedding=embedding,
                    confidence=confidence,
                )
            except Exception:
                logger.warning(
                    "Failed to resolve/insert claim %r for paper %s",
                    raw_claim,
                    paper_id,
                    exc_info=True,
                )
                continue

            inserted_claims.append({**claim, "embedding": embedding})

    return {"claims": inserted_claims}
