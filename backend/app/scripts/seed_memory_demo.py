"""Seed a realistic demo memory graph so the Memory Inspector is populated
even in echo mode (no AWS credentials / no chat turns yet run).

Usage::

    python -m app.scripts.seed_memory_demo

Populates ``memory_notes``/``memory_links``/``memory_audit_log`` for the
same demo user the chat API resolves via
``app.memory.db.users_repo.ensure_demo_user`` -- reused here rather than
re-derived, so the seeded graph shows up for whichever session hits
``/api/memory/*`` or the chat routes.

Content is drawn from the agent-memory research literature this project
itself is about (MemGPT, Mem0, Zep, A-MEM, Generative Agents, HippoRAG,
plus the user's own stated research interests and open questions) so the
Memory Inspector demo reads as a plausible slice of a real research
session rather than lorem ipsum.

Embeddings: real Titan is attempted only when
``Settings.has_aws_credentials`` looks true (mirroring the gate every
other Bedrock call site in this app uses -- see
``app.core.nodes.chat.agent_node``); on any failure this falls back to a
deterministic pseudo-random unit vector seeded from a hash of the note's
text, so the script runs fully offline and reproducibly. Either way,
every vector passes through ``normalize_embedding`` before storage, same
as the real write path.

History realism: beyond ~12 "current belief" active notes, this also
seeds one UPDATE lineage (an archived predecessor note superseded by a
refined successor, linked via ``derived_from`` + an "update" audit row
with a before/after ``details`` snapshot) and one INVALIDATE pair (an
invalidated note contradicted by a corrected successor, linked via a
``contradicts`` memory_link + an "invalidate" audit row), several
same-topic links between related notes, and a spread of "read" audit rows
standing in for retrieval-triggered reinforcement over the past few days.

Notes/links/audit rows are inserted with raw SQL (not
``app.memory.db.notes_repo``) specifically so ``created_at``/
``last_accessed_at``/``expired_at``/``invalid_at`` can be back-dated --
the repo layer's ``insert_note`` always stamps "now" server-side. The
whole reseed (clear + insert) runs as one retried transaction via
``run_transaction_async``, same retry semantics as the rest of
``app.memory.db``.

Idempotent-ish: every run first deletes any existing memory rows for the
demo user (notes/links/audit), then reinserts the full demo graph from
scratch -- safe because this app has exactly one (demo) user in Week 1/2,
so "clear this user's memory" and "clear the seed data" are the same
thing.
"""

import asyncio
import hashlib
import json
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import get_settings
from app.memory.db.chunks_repo import format_vector_literal
from app.memory.db.engine import get_engine
from app.memory.db.retry import run_transaction_async
from app.memory.db.users_repo import ensure_demo_user
from app.memory.db.vectorstore import normalize_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ACTOR = "system:seed_memory_demo"


# ---------------------------------------------------------------------------
# Embeddings: real Titan when plausible, deterministic offline fallback else.
# ---------------------------------------------------------------------------


def _deterministic_embedding(text_value: str, dim: int) -> list[float]:
    """A stable pseudo-random unit-ish vector, seeded from a hash of ``text_value``.

    Not a real embedding -- vectors for unrelated texts are not meaningfully
    close/far -- but stable across runs and requires no network/credentials,
    which is all this offline seed script needs.
    """
    seed = int(hashlib.sha256(text_value.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


async def _embed(text_value: str) -> list[float]:
    """Embed via Titan if AWS looks configured, else a deterministic fallback."""
    settings = get_settings()
    if settings.has_aws_credentials:
        try:
            from app.core.models.llm import get_embeddings

            embeddings = get_embeddings()
            raw = await asyncio.to_thread(embeddings.embed_query, text_value)
            return normalize_embedding(raw)
        except Exception:
            logger.warning(
                "Titan embedding call failed; falling back to a deterministic "
                "pseudo-embedding for %r",
                text_value[:60],
                exc_info=True,
            )
    return normalize_embedding(_deterministic_embedding(text_value, settings.EMBED_DIM))


# ---------------------------------------------------------------------------
# Raw SQL helpers (back-dated timestamps; notes_repo always stamps "now").
# ---------------------------------------------------------------------------


async def _clear_demo_memory(conn: AsyncConnection, user_id: uuid.UUID) -> dict[str, int]:
    """Delete any previously-seeded memory rows for the demo user."""
    counts: dict[str, int] = {}

    result = await conn.execute(
        text("DELETE FROM memory_audit_log WHERE user_id = :uid"), {"uid": str(user_id)}
    )
    counts["audit_deleted"] = result.rowcount or 0

    result = await conn.execute(
        text(
            "DELETE FROM memory_links WHERE source_note_id IN "
            "(SELECT id FROM memory_notes WHERE user_id = :uid) "
            "OR target_note_id IN (SELECT id FROM memory_notes WHERE user_id = :uid)"
        ),
        {"uid": str(user_id)},
    )
    counts["links_deleted"] = result.rowcount or 0

    result = await conn.execute(
        text("DELETE FROM memory_notes WHERE user_id = :uid"), {"uid": str(user_id)}
    )
    counts["notes_deleted"] = result.rowcount or 0

    return counts


async def _insert_note(
    conn: AsyncConnection,
    *,
    user_id: uuid.UUID,
    content: str,
    embedding: list[float],
    keywords: list[str],
    tags: list[str],
    context: str | None,
    importance: float,
    strength: float,
    access_count: int,
    is_user_stated: bool,
    derived_from: list[uuid.UUID],
    status: str,
    created_at: datetime,
    last_accessed_at: datetime,
    valid_at: datetime,
    invalid_at: datetime | None,
    expired_at: datetime | None,
    confidence: float = 0.8,
) -> uuid.UUID:
    note_id = uuid.uuid4()
    await conn.execute(
        text(
            """
            INSERT INTO memory_notes
                (id, user_id, content, keywords, tags, context, embedding,
                 importance, strength, last_accessed_at, access_count, confidence,
                 is_user_stated, source_episode_id, derived_from, status,
                 valid_at, invalid_at, created_at, expired_at)
            VALUES
                (:id, :user_id, :content, :keywords, :tags, :context,
                 CAST(:embedding AS VECTOR),
                 :importance, :strength, :last_accessed_at, :access_count, :confidence,
                 :is_user_stated, NULL, CAST(:derived_from AS UUID[]), :status,
                 :valid_at, :invalid_at, :created_at, :expired_at)
            """
        ),
        {
            "id": str(note_id),
            "user_id": str(user_id),
            "content": content,
            "keywords": keywords,
            "tags": tags,
            "context": context,
            "embedding": format_vector_literal(embedding),
            "importance": importance,
            "strength": strength,
            "last_accessed_at": last_accessed_at,
            "access_count": access_count,
            "confidence": confidence,
            "is_user_stated": is_user_stated,
            "derived_from": [str(x) for x in derived_from],
            "status": status,
            "valid_at": valid_at,
            "invalid_at": invalid_at,
            "created_at": created_at,
            "expired_at": expired_at,
        },
    )
    return note_id


async def _insert_link(
    conn: AsyncConnection,
    *,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    relation_type: str,
    weight: float,
    created_at: datetime,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO memory_links
                (id, source_note_id, target_note_id, relation_type, weight, created_at)
            VALUES (:id, :source, :target, :relation_type, :weight, :created_at)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "source": str(source_id),
            "target": str(target_id),
            "relation_type": relation_type,
            "weight": weight,
            "created_at": created_at,
        },
    )


async def _insert_audit(
    conn: AsyncConnection,
    *,
    user_id: uuid.UUID,
    action: str,
    target_id: uuid.UUID,
    reason: str,
    details: dict[str, Any],
    created_at: datetime,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO memory_audit_log
                (id, user_id, actor, action, target_table, target_id, reason, details, created_at)
            VALUES
                (:id, :user_id, :actor, :action, 'memory_notes', :target_id, :reason,
                 CAST(:details AS JSONB), :created_at)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "actor": _ACTOR,
            "action": action,
            "target_id": str(target_id),
            "reason": reason,
            "details": json.dumps(details, default=str),
            "created_at": created_at,
        },
    )


def _summary(note_id: uuid.UUID, content: str, importance: float) -> dict[str, Any]:
    """A compact before/after snapshot for update/invalidate audit ``details``."""
    return {"id": str(note_id), "content": content, "importance": importance}


# ---------------------------------------------------------------------------
# Demo content: agent-memory research theme.
# ---------------------------------------------------------------------------

# "Plain" active notes -- no lineage, just current beliefs at varying ages.
# Each has a short, unique "key" (not stored in the DB) used only to wire up
# the same_topic links below without relying on fragile content-string matching.
_PLAIN_NOTES = [
    dict(
        key="memgpt",
        content=(
            "MemGPT treats the LLM context window like an OS manages virtual memory: "
            "it pages facts in and out of the prompt, moving overflow into an external "
            "'archival'/'recall' store and paging it back in when relevant."
        ),
        keywords=["memgpt", "context window", "paging"],
        tags=["memgpt", "paging"],
        context="Packer et al., 2023 -- MemGPT: Towards LLMs as Operating Systems",
        importance=0.7,
        strength=2.0,
        access_count=2,
        is_user_stated=False,
        age_days=6,
    ),
    dict(
        key="zep",
        content=(
            "Zep models agent memory as a bi-temporal knowledge graph, tracking both "
            "event time (when something became true) and ingestion time (when the "
            "system learned it), so past belief states can be reconstructed exactly."
        ),
        keywords=["zep", "bi-temporal", "knowledge graph"],
        tags=["zep", "bitemporal"],
        context="Zep: A Temporal Knowledge Graph Architecture for Agent Memory",
        importance=0.65,
        strength=1.5,
        access_count=1,
        is_user_stated=False,
        age_days=5,
    ),
    dict(
        key="a_mem",
        content=(
            "A-MEM builds a Zettelkasten-style note graph for agent memory: each new "
            "memory dynamically generates links to related existing notes instead of "
            "relying on a fixed schema, letting structure emerge from usage."
        ),
        keywords=["a-mem", "zettelkasten", "note graph"],
        tags=["a-mem", "graph"],
        context="A-MEM: Agentic Memory for LLM Agents",
        importance=0.6,
        strength=1.4,
        access_count=1,
        is_user_stated=False,
        age_days=5,
    ),
    dict(
        key="genagents",
        content=(
            "Generative Agents (Park et al.) score candidate memories for retrieval "
            "with a weighted sum of recency, importance, and relevance, then pull the "
            "top-scoring memories into the prompt each turn."
        ),
        keywords=["generative agents", "scoring", "retrieval"],
        tags=["generative-agents", "scoring"],
        context="Park et al., 2023 -- Generative Agents: Interactive Simulacra of Human Behavior",
        importance=0.8,
        strength=3.0,
        access_count=3,
        is_user_stated=False,
        age_days=4,
    ),
    dict(
        key="interest_contradiction",
        content=(
            "I'm most interested in how memory systems handle contradiction and "
            "forgetting, not just retrieval accuracy -- most papers focus on recall@k "
            "and barely discuss what happens when a fact turns out to be wrong."
        ),
        keywords=["contradiction", "forgetting", "research interest"],
        tags=["research-interest", "contradiction", "forgetting"],
        context=None,
        importance=0.9,
        strength=1.8,
        access_count=2,
        is_user_stated=True,
        age_days=3,
    ),
    dict(
        key="interest_decay",
        content=(
            "I want to compare Ebbinghaus-style exponential decay against simple "
            "linear recency-weighted decay for memory scoring -- unclear if the extra "
            "modeling complexity actually improves retrieval quality in practice."
        ),
        keywords=["ebbinghaus", "decay", "research interest"],
        tags=["research-interest", "decay", "scoring"],
        context=None,
        importance=0.85,
        strength=1.3,
        access_count=1,
        is_user_stated=True,
        age_days=2,
    ),
    dict(
        key="open_q_update_vs_invalidate",
        content=(
            "Open question: how should a memory system decide between UPDATE (refine "
            "an existing note) vs INVALIDATE (mark it contradicted) when a new fact "
            "only partially conflicts with an old one?"
        ),
        keywords=["update", "invalidate", "open question"],
        tags=["open-question", "consolidation"],
        context=None,
        importance=0.55,
        strength=1.0,
        access_count=0,
        is_user_stated=False,
        age_days=2,
    ),
    dict(
        key="open_q_link_fanout",
        content=(
            "Open question: is there a principled way to bound memory_links fan-out "
            "per note so graph traversal at retrieval time doesn't degrade as the "
            "memory graph grows over a long-running session?"
        ),
        keywords=["links", "fan-out", "open question"],
        tags=["open-question", "graph", "scaling"],
        context=None,
        importance=0.5,
        strength=1.0,
        access_count=0,
        is_user_stated=False,
        age_days=1,
    ),
    dict(
        key="ebbinghaus",
        content=(
            "The Ebbinghaus forgetting curve models retention as R = e^(-t/S), where "
            "t is elapsed time and S is memory strength -- several agent-memory papers "
            "borrow this directly as a recency/decay term in their scoring function."
        ),
        keywords=["ebbinghaus", "forgetting curve", "retention"],
        tags=["ebbinghaus", "decay", "scoring"],
        context="Ebbinghaus (1885) forgetting curve, applied to agent memory scoring",
        importance=0.6,
        strength=1.6,
        access_count=2,
        is_user_stated=False,
        age_days=1,
    ),
    dict(
        key="reflection",
        content=(
            "Reflection mechanisms (as in Generative Agents) periodically synthesize "
            "higher-level insights from a stream of lower-level observations, then "
            "store those reflections back into memory for future retrieval."
        ),
        keywords=["reflection", "synthesis", "observations"],
        tags=["reflection", "generative-agents", "synthesis"],
        context="Park et al., 2023 -- Generative Agents reflection tree",
        importance=0.65,
        strength=1.3,
        access_count=1,
        is_user_stated=False,
        age_days=0,
    ),
]


async def _seed_body(conn: AsyncConnection, user_id: uuid.UUID, now: datetime) -> dict[str, Any]:
    cleared = await _clear_demo_memory(conn, user_id)

    note_ids: dict[str, uuid.UUID] = {}
    read_audit_plan: list[tuple[uuid.UUID, datetime]] = []
    add_audit_count = 0

    # -- 10 plain "current belief" notes --------------------------------
    for spec in _PLAIN_NOTES:
        created_at = now - timedelta(days=spec["age_days"], hours=spec["age_days"] % 3)
        embedding = await _embed(spec["content"])
        note_id = await _insert_note(
            conn,
            user_id=user_id,
            content=spec["content"],
            embedding=embedding,
            keywords=spec["keywords"],
            tags=spec["tags"],
            context=spec["context"],
            importance=spec["importance"],
            strength=spec["strength"],
            access_count=spec["access_count"],
            is_user_stated=spec["is_user_stated"],
            derived_from=[],
            status="active",
            created_at=created_at,
            last_accessed_at=now,
            valid_at=created_at,
            invalid_at=None,
            expired_at=None,
        )
        note_ids[spec["key"]] = note_id
        await _insert_audit(
            conn,
            user_id=user_id,
            action="add",
            target_id=note_id,
            reason="new fact; no sufficiently similar existing note",
            details={"after": _summary(note_id, spec["content"], spec["importance"])},
            created_at=created_at,
        )
        add_audit_count += 1
        for i in range(spec["access_count"]):
            frac = (i + 1) / (spec["access_count"] + 1)
            read_audit_plan.append((note_id, created_at + (now - created_at) * frac))

    # -- UPDATE lineage: archived predecessor -> refined successor --------
    predecessor_created = now - timedelta(days=6)
    predecessor_content = "Mem0 just deduplicates facts by overwriting anything similar."
    predecessor_embedding = await _embed(predecessor_content)
    update_at = now - timedelta(days=2)
    predecessor_id = await _insert_note(
        conn,
        user_id=user_id,
        content=predecessor_content,
        embedding=predecessor_embedding,
        keywords=["mem0", "consolidation"],
        tags=["mem0", "consolidation"],
        context="Mem0 (mem0.ai) memory layer for AI agents",
        importance=0.5,
        strength=1.0,
        access_count=1,
        is_user_stated=False,
        derived_from=[],
        status="archived",
        created_at=predecessor_created,
        last_accessed_at=update_at,
        valid_at=predecessor_created,
        invalid_at=None,
        expired_at=update_at,
    )
    await _insert_audit(
        conn,
        user_id=user_id,
        action="add",
        target_id=predecessor_id,
        reason="new fact; no sufficiently similar existing note",
        details={"after": _summary(predecessor_id, predecessor_content, 0.5)},
        created_at=predecessor_created,
    )
    add_audit_count += 1

    successor_content = (
        "Mem0 performs an LLM-based ADD/UPDATE/DELETE/NOOP decision per extracted "
        "fact rather than blindly overwriting, so it can keep, refine, or reinforce "
        "existing memories instead of just deduplicating them."
    )
    successor_embedding = await _embed(successor_content)
    mem0_successor_id = await _insert_note(
        conn,
        user_id=user_id,
        content=successor_content,
        embedding=successor_embedding,
        keywords=["mem0", "consolidation", "add/update"],
        tags=["mem0", "consolidation"],
        context="Mem0 (mem0.ai) memory layer for AI agents",
        importance=0.75,
        strength=1.4,
        access_count=1,
        is_user_stated=False,
        derived_from=[predecessor_id],
        status="active",
        created_at=update_at,
        last_accessed_at=now,
        valid_at=update_at,
        invalid_at=None,
        expired_at=None,
    )
    await _insert_audit(
        conn,
        user_id=user_id,
        action="update",
        target_id=mem0_successor_id,
        reason="Refined understanding of Mem0's consolidation decision logic after rereading it.",
        details={
            "before": _summary(predecessor_id, predecessor_content, 0.5),
            "after": _summary(mem0_successor_id, successor_content, 0.75),
        },
        created_at=update_at,
    )
    read_audit_plan.append((mem0_successor_id, now - timedelta(hours=6)))

    # -- INVALIDATE pair: wrong note contradicted by a corrected successor -
    invalidated_created = now - timedelta(days=5)
    invalidated_content = (
        "HippoRAG is mainly a recommendation-system technique, not really about "
        "RAG retrieval."
    )
    invalidated_embedding = await _embed(invalidated_content)
    invalidate_at = now - timedelta(days=1)
    invalidated_id = await _insert_note(
        conn,
        user_id=user_id,
        content=invalidated_content,
        embedding=invalidated_embedding,
        keywords=["hipporag"],
        tags=["hipporag"],
        context="HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs",
        importance=0.4,
        strength=1.0,
        access_count=1,
        is_user_stated=False,
        derived_from=[],
        status="invalidated",
        created_at=invalidated_created,
        last_accessed_at=invalidate_at,
        valid_at=invalidated_created,
        invalid_at=invalidate_at,
        expired_at=invalidate_at,
    )
    await _insert_audit(
        conn,
        user_id=user_id,
        action="add",
        target_id=invalidated_id,
        reason="new fact; no sufficiently similar existing note",
        details={"after": _summary(invalidated_id, invalidated_content, 0.4)},
        created_at=invalidated_created,
    )
    add_audit_count += 1

    hipporag_content = (
        "HippoRAG uses a hippocampus-inspired knowledge graph plus personalized "
        "PageRank for efficient single-step multi-hop retrieval-augmented generation."
    )
    hipporag_embedding = await _embed(hipporag_content)
    hipporag_successor_id = await _insert_note(
        conn,
        user_id=user_id,
        content=hipporag_content,
        embedding=hipporag_embedding,
        keywords=["hipporag", "knowledge graph", "pagerank"],
        tags=["hipporag", "graph", "multi-hop"],
        context="HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs",
        importance=0.6,
        strength=1.3,
        access_count=1,
        is_user_stated=False,
        derived_from=[],
        status="active",
        created_at=invalidate_at,
        last_accessed_at=now,
        valid_at=invalidate_at,
        invalid_at=None,
        expired_at=None,
    )
    await _insert_audit(
        conn,
        user_id=user_id,
        action="invalidate",
        target_id=hipporag_successor_id,
        reason="Corrected mischaracterization of HippoRAG as a recommendation technique.",
        details={
            "before": _summary(invalidated_id, invalidated_content, 0.4),
            "after": _summary(hipporag_successor_id, hipporag_content, 0.6),
        },
        created_at=invalidate_at,
    )
    await _insert_link(
        conn,
        source_id=hipporag_successor_id,
        target_id=invalidated_id,
        relation_type="contradicts",
        weight=1.0,
        created_at=invalidate_at,
    )
    read_audit_plan.append((hipporag_successor_id, now - timedelta(hours=3)))

    # -- same_topic links between related active notes --------------------
    same_topic_links = [
        (note_ids["memgpt"], mem0_successor_id, 0.78),
        (note_ids["a_mem"], note_ids["genagents"], 0.81),
        (note_ids["zep"], hipporag_successor_id, 0.76),
        (note_ids["ebbinghaus"], note_ids["genagents"], 0.88),
        (note_ids["reflection"], note_ids["genagents"], 0.92),
        (note_ids["open_q_update_vs_invalidate"], mem0_successor_id, 0.80),
    ]
    for source_id, target_id, weight in same_topic_links:
        await _insert_link(
            conn,
            source_id=source_id,
            target_id=target_id,
            relation_type="same_topic",
            weight=weight,
            created_at=now - timedelta(hours=random.randint(1, 48)),
        )

    # -- read (reinforcement) audit rows -----------------------------------
    for note_id, ts in read_audit_plan:
        await _insert_audit(
            conn,
            user_id=user_id,
            action="read",
            target_id=note_id,
            reason="retrieved for chat",
            details={"score": round(random.uniform(0.55, 0.95), 3)},
            created_at=ts,
        )

    # + predecessor, mem0 successor, invalidated note, hipporag successor.
    notes_inserted = len(_PLAIN_NOTES) + 4
    links_inserted = len(same_topic_links) + 1  # + the contradicts link
    # add-audits + 1 update-audit + 1 invalidate-audit + read-audits.
    audit_inserted = add_audit_count + 1 + 1 + len(read_audit_plan)
    return {
        **cleared,
        "notes_inserted": notes_inserted,
        "links_inserted": links_inserted,
        "audit_inserted": audit_inserted,
    }


async def seed() -> dict[str, Any]:
    """Clear and reseed the demo memory graph; returns a summary dict."""
    user_id = await ensure_demo_user()
    engine = get_engine()
    now = datetime.now(UTC)

    async def _do() -> dict[str, Any]:
        async with engine.engine.begin() as conn:
            return await _seed_body(conn, user_id, now)

    summary = await run_transaction_async(_do)

    from app.memory.db import notes_repo

    stats = await notes_repo.stats(user_id)
    summary["stats"] = stats
    return summary


async def main() -> None:
    summary = await seed()
    logger.info("Seeded demo memory graph for user %s", summary)
    print("Seed summary:")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
