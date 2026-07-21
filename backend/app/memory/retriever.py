"""Memory-retrieval path: ANN search + Ebbinghaus/importance/relevance rescoring.

``retrieve_and_reinforce`` is what ``retrieve_node`` calls each turn:

1. Embed the query (Titan + ``normalize_embedding``).
2. ANN search the top-``ann_limit`` ACTIVE, temporally-valid notes for the
   user (``notes_repo.search_similar_active_notes`` already applies the
   ``valid_at <= now() AND (invalid_at IS NULL OR invalid_at > now())``
   filter).
3. Rescore every candidate with ``app.memory.scoring.combined_score``,
   using Ebbinghaus retention for recency, the stored ``importance``, and
   ``1 - distance^2/2`` (cosine similarity for unit vectors) for relevance.
4. Keep the top ``top_k``, reinforce each (bump strength/access_count/
   last_accessed_at) and write a ``read`` audit row with the score
   breakdown.

``score_candidates`` is split out as a pure function (no I/O) so scoring
order/weights are unit-testable without a database.

Optional multi-hop expansion (Week 3): after scoring, the top vector hits
are used as seeds into ``app.memory.graph_traversal.expand_via_links``
(1-hop by default), and any newly-reached notes are folded into the
candidate pool with an approximate relevance (propagated from the seed
that reached them, decayed by the graph path weight) before the final
top-``top_k`` cut. This is gated behind ``MULTIHOP_ENABLED`` (env var,
default on) and wrapped in a try/except so any failure -- traversal error,
a note that's since been archived, graph_traversal missing/broken --
falls back to exactly the plain vector+scoring result, never raising out
of ``retrieve_and_reinforce``.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from app.memory import audit
from app.memory.db import notes_repo
from app.memory.db.vectorstore import normalize_embedding
from app.memory.scoring import (
    combined_score,
    ebbinghaus_retention,
    l2_distance_to_cosine_similarity,
    reinforce,
)

logger = logging.getLogger(__name__)

ANN_LIMIT = 20
TOP_K = 5

# Multi-hop graph expansion tuning.
MULTIHOP_HOPS = 1
MULTIHOP_SEED_COUNT = 5
MULTIHOP_NEIGHBOR_LIMIT = 20
MULTIHOP_RELEVANCE_BOOST = 0.05

_ACTOR = "system:retriever"


def _multihop_enabled() -> bool:
    """Read ``MULTIHOP_ENABLED`` directly from the environment (default on).

    Deliberately bypasses ``app.core.config.Settings`` so enabling/disabling
    multi-hop expansion doesn't require a config.py change -- this flag is
    read fresh on every call, which also makes it trivial to toggle in
    tests via ``monkeypatch.setenv``.
    """
    return os.getenv("MULTIHOP_ENABLED", "true").strip().lower() not in ("0", "false", "no")


def score_candidates(
    candidates: list[dict[str, Any]], *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Rescore ANN candidates by combined (recency, importance, relevance) score.

    Each input dict must have ``strength``, ``last_accessed_at``,
    ``importance``, and ``distance`` (L2 distance from the query vector,
    as returned by ``notes_repo.search_similar_active_notes``). Returns a
    new list (input is not mutated) sorted by score descending, with
    ``recency``/``relevance``/``score`` attached to each entry.
    """
    now = now or datetime.now(UTC)
    scored = []
    for candidate in candidates:
        last_accessed = candidate["last_accessed_at"]
        dt_seconds = (now - last_accessed).total_seconds()
        recency = ebbinghaus_retention(dt_seconds, candidate["strength"])
        relevance = l2_distance_to_cosine_similarity(candidate["distance"])
        score = combined_score(recency, candidate["importance"], relevance)
        scored.append({**candidate, "recency": recency, "relevance": relevance, "score": score})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored


async def _reinforce_and_audit(user_id: str, note: dict[str, Any]) -> None:
    new_strength = reinforce(note["strength"], note["access_count"])
    await notes_repo.reinforce_note(
        note["id"], new_strength=new_strength, new_access_count=note["access_count"] + 1
    )
    await audit.write_audit(
        None,
        user_id=user_id,
        actor=_ACTOR,
        action="read",
        target_table="memory_notes",
        target_id=note["id"],
        reason="retrieved for chat",
        details={
            "score": note["score"],
            "recency": note["recency"],
            "importance": note["importance"],
            "relevance": note["relevance"],
        },
    )


async def _expand_with_graph(user_id: str, scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold graph-neighbor notes into ``scored`` via 1-hop expansion from the top hits.

    Uses the top ``MULTIHOP_SEED_COUNT`` vector hits as seeds into
    ``graph_traversal.expand_via_links``. Neighbors not already in the
    candidate pool are fetched (``notes_repo.get_note``) and assigned an
    approximate relevance -- the average relevance of the seed hits, decayed
    by the graph path weight, plus a small constant boost -- since they
    weren't matched by vector similarity directly. Returns a new list
    (re-sorted by score); raises on any failure so the caller's try/except
    can fall back to the plain vector-only ``scored`` list unchanged.
    """
    from app.memory import graph_traversal

    seed_ids = [c["id"] for c in scored[:MULTIHOP_SEED_COUNT]]
    if not seed_ids:
        return scored

    expanded = await graph_traversal.expand_via_links(
        user_id, seed_ids, hops=MULTIHOP_HOPS, limit=MULTIHOP_NEIGHBOR_LIMIT
    )
    if not expanded:
        return scored

    existing_ids = {c["id"] for c in scored}
    avg_relevance = sum(c["relevance"] for c in scored[:MULTIHOP_SEED_COUNT]) / len(seed_ids)
    now = datetime.now(UTC)

    folded = list(scored)
    for neighbor in expanded:
        note_id = neighbor["note_id"]
        if note_id in existing_ids:
            continue
        note = await notes_repo.get_note(note_id)
        if note is None:
            continue

        recency = ebbinghaus_retention(
            (now - note["last_accessed_at"]).total_seconds(), note["strength"]
        )
        relevance = min(1.0, avg_relevance * neighbor["path_weight"] + MULTIHOP_RELEVANCE_BOOST)
        score = combined_score(recency, note["importance"], relevance)
        folded.append(
            {
                **note,
                "distance": None,
                "recency": recency,
                "relevance": relevance,
                "score": score,
                "via_graph_hops": neighbor["hops"],
            }
        )
        existing_ids.add(note_id)

    folded.sort(key=lambda c: c["score"], reverse=True)
    return folded


async def retrieve_and_reinforce(
    user_id: str,
    query_text: str,
    *,
    ann_limit: int = ANN_LIMIT,
    top_k: int = TOP_K,
    embed_fn: Any = None,
) -> list[dict[str, Any]]:
    """Retrieve the top-``top_k`` memory notes relevant to ``query_text``, reinforcing each."""
    if embed_fn is not None:
        raw = embed_fn(query_text)
        if asyncio.iscoroutine(raw):
            raw = await raw
    else:
        from app.core.models.llm import get_embeddings

        embeddings = get_embeddings()
        raw = await asyncio.to_thread(embeddings.embed_query, query_text)
    query_vector = normalize_embedding(raw)

    candidates = await notes_repo.search_similar_active_notes(
        user_id, query_vector, limit=ann_limit
    )
    if not candidates:
        return []

    scored = score_candidates(candidates)

    if _multihop_enabled():
        try:
            scored = await _expand_with_graph(user_id, scored)
        except Exception:
            logger.warning(
                "Multi-hop graph expansion failed; falling back to vector-only ranking",
                exc_info=True,
            )

    top = scored[:top_k]

    for note in top:
        try:
            await _reinforce_and_audit(user_id, note)
        except Exception:
            # Reinforcement/audit failure shouldn't drop the note from this
            # turn's context -- it's still the best-scored match we found.
            logger.warning(
                "Failed to reinforce/audit retrieved note %s", note.get("id"), exc_info=True
            )

    return top
