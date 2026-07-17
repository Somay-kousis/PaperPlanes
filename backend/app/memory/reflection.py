"""Reflection generation: the "sleep-time compute" cycle (Week 3).

``run_reflection_cycle`` is the single entry point both the demo
``POST /api/reflections/run`` route and the background scheduler
(``app.workers.reflection_worker``) call. Each cycle runs two independent,
self-degrading passes over one user's active memory:

1. **Decay pass** (``_decay_pass``): recompute each active note's effective
   Ebbinghaus retention (``app.memory.scoring.ebbinghaus_retention``) given
   how long it's been since it was last accessed. Notes that have decayed
   below ``DECAY_ARCHIVE_THRESHOLD``, have been accessed only rarely
   (``access_count <= DECAY_MAX_ACCESS_COUNT``), and are older than
   ``DECAY_MIN_AGE`` (so brand-new notes are never swept up before anyone's
   had a chance to reinforce them) are soft-archived via
   ``notes_repo.archive_note`` and audited with ``action="archive"``.

2. **Reflection pass** (``_reflection_pass``): gathers the top active notes
   by importance, gates on whether enough *new* importance has accumulated
   since the last reflection (``REFLECTION_IMPORTANCE_GATE`` -- skipped for
   non-manual triggers below the gate, always run for a manual trigger),
   then asks the fast Bedrock model (Nova Lite via ``get_fast_model()``)
   for 1-3 higher-level insight statements, each citing the note ids it
   drew from. Nova (like any LLM) can hallucinate ids that were never
   offered to it, so every citation is validated against the actual input
   note-id set; insights left with zero valid citations after that
   filtering are dropped rather than persisted as an unattributed
   assertion. Surviving insights are embedded (normalized) and persisted
   via ``reflections_repo.insert_reflection``, audited with
   ``target_table="reflections"``.

Both passes -- and the model call inside the reflection pass -- are
wrapped so that any failure (DB down, AWS/model unavailable, malformed
model output) degrades the *count* for that piece to zero rather than
raising; ``run_reflection_cycle`` itself never raises out to its caller,
mirroring ``app.memory.writer``/``app.core.nodes.chat.extract_facts_node``'s
"never crash the caller" philosophy. ``contradictions_found`` is always 0
here -- claim-level contradiction detection at ingestion is Agent A's
``app.memory.contradiction`` module, not this one.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.memory import audit
from app.memory.db import notes_repo, reflections_repo
from app.memory.db.vectorstore import normalize_embedding
from app.memory.scoring import ebbinghaus_retention

logger = logging.getLogger(__name__)

# --- Decay pass ------------------------------------------------------------

DECAY_ARCHIVE_THRESHOLD = 0.05
# "Accessed only rarely" -- notes reinforced more than this many times have
# demonstrated ongoing relevance and are left alone even if retention is low.
DECAY_MAX_ACCESS_COUNT = 1
# Never archive a note before it's had a chance to be reinforced at all.
DECAY_MIN_AGE = timedelta(hours=24)
DECAY_SCAN_LIMIT = 500

# --- Reflection pass ---------------------------------------------------------

REFLECTION_IMPORTANCE_GATE = 3.0
TOP_NOTES_FOR_REFLECTION = 15
MAX_INSIGHTS = 3
REFLECTION_SCAN_LIMIT = 200

_ACTOR = "system:reflection_worker"

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "core" / "prompts" / "reflection.md"


@lru_cache
def _load_reflection_prompt() -> str:
    return _PROMPT_PATH.read_text()


class ReflectionInsight(BaseModel):
    """A single higher-level insight, as extracted by the fast model."""

    content: str
    cites: list[str] = Field(default_factory=list)


class ReflectionInsights(BaseModel):
    """Structured-output container: 1-3 insights synthesized from recent notes."""

    insights: list[ReflectionInsight] = Field(default_factory=list)


async def _embed(text_value: str, embed_fn: Any) -> list[float]:
    if embed_fn is not None:
        raw = embed_fn(text_value)
        if asyncio.iscoroutine(raw):
            raw = await raw
        return normalize_embedding(raw)

    from app.core.models.llm import get_embeddings

    embeddings = get_embeddings()
    raw = await asyncio.to_thread(embeddings.embed_query, text_value)
    return normalize_embedding(raw)


async def _decay_pass(user_id: str, *, now: datetime) -> int:
    """Archive active notes that have decayed past the retention threshold."""
    try:
        notes = await notes_repo.list_notes(user_id, status="active", limit=DECAY_SCAN_LIMIT)
    except Exception:
        logger.warning("Decay pass: failed to list active notes", exc_info=True)
        return 0

    archived = 0
    for note in notes:
        if now - note["created_at"] < DECAY_MIN_AGE:
            continue
        if note["access_count"] > DECAY_MAX_ACCESS_COUNT:
            continue
        dt_seconds = (now - note["last_accessed_at"]).total_seconds()
        retention = ebbinghaus_retention(dt_seconds, note["strength"])
        if retention >= DECAY_ARCHIVE_THRESHOLD:
            continue

        try:
            await notes_repo.archive_note(note["id"])
            await audit.write_audit(
                None,
                user_id=user_id,
                actor=_ACTOR,
                action="archive",
                target_table="memory_notes",
                target_id=note["id"],
                reason=(
                    f"decay: retention={retention:.4f} below threshold "
                    f"{DECAY_ARCHIVE_THRESHOLD} (access_count={note['access_count']})"
                ),
                details={
                    "retention": retention,
                    "strength": note["strength"],
                    "access_count": note["access_count"],
                },
            )
            archived += 1
        except Exception:
            logger.warning(
                "Decay pass: failed to archive/audit note %s", note.get("id"), exc_info=True
            )

    return archived


def _select_reflection_notes(active_notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Top notes by importance (ties broken by recency), for the reflection prompt."""
    return sorted(
        active_notes, key=lambda n: (n["importance"], n["created_at"]), reverse=True
    )[:TOP_NOTES_FOR_REFLECTION]


async def _generate_insights(
    notes: list[dict[str, Any]], *, decision_model: Any
) -> ReflectionInsights:
    """Call the fast model for structured reflection insights; degrade to empty on failure."""
    model = decision_model
    if model is None:
        from app.core.models.llm import get_fast_model

        model = get_fast_model()
    structured = model.with_structured_output(ReflectionInsights)
    prompt = _load_reflection_prompt().format(
        notes=json.dumps([{"id": n["id"], "content": n["content"]} for n in notes])
    )
    result = await asyncio.to_thread(structured.invoke, prompt)
    if not isinstance(result, ReflectionInsights):
        result = ReflectionInsights.model_validate(result)
    return result


async def _reflection_pass(
    user_id: str,
    *,
    now: datetime,
    trigger_reason: str,
    embed_fn: Any,
    decision_model: Any,
) -> int:
    """Synthesize and persist 0-``MAX_INSIGHTS`` reflections from recent important notes."""
    try:
        recent_reflections = await reflections_repo.list_reflections(user_id, limit=1)
    except Exception:
        logger.warning("Reflection pass: failed to check last reflection time", exc_info=True)
        recent_reflections = []
    last_reflection_at = recent_reflections[0]["created_at"] if recent_reflections else None

    try:
        active_notes = await notes_repo.list_notes(
            user_id, status="active", limit=REFLECTION_SCAN_LIMIT
        )
    except Exception:
        logger.warning("Reflection pass: failed to list active notes", exc_info=True)
        return 0

    if not active_notes:
        return 0

    if last_reflection_at is not None:
        new_notes = [n for n in active_notes if n["created_at"] > last_reflection_at]
    else:
        new_notes = active_notes
    new_importance = sum(n["importance"] for n in new_notes)

    if trigger_reason != "manual" and new_importance < REFLECTION_IMPORTANCE_GATE:
        return 0

    top_notes = _select_reflection_notes(active_notes)
    if not top_notes:
        return 0

    try:
        insights = await _generate_insights(top_notes, decision_model=decision_model)
    except Exception:
        logger.warning("Reflection pass: model call failed; skipping this cycle", exc_info=True)
        return 0

    valid_ids = {n["id"] for n in top_notes}
    notes_by_id = {n["id"]: n for n in top_notes}
    created = 0

    for insight in insights.insights[:MAX_INSIGHTS]:
        content = (insight.content or "").strip()
        if not content:
            continue
        cites = [note_id for note_id in insight.cites if note_id in valid_ids]
        # An insight with no citation that survives validation can't be
        # attributed to any real note -- drop it rather than persist an
        # ungrounded (possibly fully-hallucinated) assertion.
        if not cites:
            continue

        importance = sum(notes_by_id[c]["importance"] for c in cites) / len(cites)
        try:
            embedding = await _embed(content, embed_fn)
            row = await reflections_repo.insert_reflection(
                user_id=user_id,
                content=content,
                cites=cites,
                trigger_reason=trigger_reason,
                importance=importance,
                embedding=embedding,
            )
            await audit.write_audit(
                None,
                user_id=user_id,
                actor=_ACTOR,
                action="add",
                target_table="reflections",
                target_id=row["id"],
                reason=f"reflection ({trigger_reason})",
                details={"cites": cites, "importance": importance},
            )
            created += 1
        except Exception:
            logger.warning("Reflection pass: failed to persist an insight", exc_info=True)

    return created


async def run_reflection_cycle(
    user_id: str,
    *,
    trigger_reason: str = "manual",
    now: datetime | None = None,
    embed_fn: Any = None,
    decision_model: Any = None,
) -> dict[str, int]:
    """Run one reflection cycle (decay pass + reflection pass) for ``user_id``.

    Never raises: a failure in either pass degrades that pass's count to 0
    rather than propagating, so a down DB or unavailable model still lets
    the rest of the cycle (and the caller) proceed normally.
    """
    now = now or datetime.now(UTC)
    result = {"reflections_created": 0, "notes_archived": 0, "contradictions_found": 0}

    try:
        result["notes_archived"] = await _decay_pass(user_id, now=now)
    except Exception:
        logger.warning("Reflection cycle: decay pass raised unexpectedly", exc_info=True)

    try:
        result["reflections_created"] = await _reflection_pass(
            user_id,
            now=now,
            trigger_reason=trigger_reason,
            embed_fn=embed_fn,
            decision_model=decision_model,
        )
    except Exception:
        logger.warning("Reflection cycle: reflection pass raised unexpectedly", exc_info=True)

    return result
