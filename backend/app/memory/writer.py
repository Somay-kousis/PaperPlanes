"""Memory-write path: dedupe, insert, update, invalidate, and reinforce notes.

``MemoryWriter.consolidate`` is the single entry point ``memory_write_node``
calls. For each candidate fact:

1. Embed its content (Titan + ``normalize_embedding``).
2. Search the top-``TOP_SIMILAR_FOR_DECISION`` similar ACTIVE notes.
3. If nothing clears ``ADD_SIMILARITY_THRESHOLD`` -> **ADD** directly,
   skipping the LLM decision call entirely (the cheap, common case: this
   is genuinely new information).
4. Otherwise, ask the fast model (``memory_decision.md``) to choose
   exactly one of ADD / UPDATE / INVALIDATE / NOOP, then apply that
   decision -- the decision call always happens *before* any row mutation,
   so no transaction is ever held open across the LLM call.

Every branch leaves an audit row (`app.memory.audit.write_audit`) and ADD/
UPDATE/INVALIDATE additionally run same-topic link generation against the
newly-written note.
"""

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.memory import audit
from app.memory.db import notes_repo
from app.memory.db.vectorstore import normalize_embedding
from app.memory.scoring import l2_distance_to_cosine_similarity, reinforce

logger = logging.getLogger(__name__)

ADD_SIMILARITY_THRESHOLD = 0.60
# When the model says INVALIDATE but its target id is untrustworthy, only snap to
# the closest note if that note is genuinely similar; otherwise ADD instead of
# fabricating a contradiction against an unrelated memory.
INVALIDATE_MIN_SIMILARITY = 0.60
LINK_SIMILARITY_THRESHOLD = 0.75
MAX_LINKS_PER_NOTE = 3
TOP_SIMILAR_FOR_DECISION = 5
LINK_SEARCH_LIMIT = MAX_LINKS_PER_NOTE + 2  # padding to allow filtering out self

_ACTOR = "system:memory_writer"

# Per-user consolidation locks. The read (ANN search) -> decide (LLM) -> apply
# window has no DB-level guard, so two concurrent turns for the SAME user (e.g.
# two open tabs) could both decide to ADD the same fact, or both INVALIDATE the
# same target, and duplicate it. Serialising a user's consolidation behind an
# in-process lock closes that window. This is process-local -- correct for the
# single-instance demo deployment; a multi-instance deployment would need a
# database advisory lock instead. Different users never block each other.
_user_locks: dict[str, asyncio.Lock] = {}


def _lock_for(user_id: str) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "core" / "prompts" / "memory_decision.md"


@lru_cache
def _load_decision_prompt() -> str:
    return _PROMPT_PATH.read_text()


class MemoryDecision(BaseModel):
    """Structured output for the memory-write decision prompt."""

    decision: Literal["ADD", "UPDATE", "INVALIDATE", "NOOP"]
    note_id: str | None = Field(default=None, description="Target note id; required unless ADD.")
    reason: str = Field(description="One-sentence justification for this decision.")


def _summarize_similar(similar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Render similar notes compactly for the decision prompt (no embeddings)."""
    return [
        {
            "id": note["id"],
            "content": note["content"],
            "importance": note["importance"],
            "similarity": round(l2_distance_to_cosine_similarity(note["distance"]), 4),
        }
        for note in similar
    ]


class MemoryWriter:
    """Consolidates extracted fact candidates into ``memory_notes``."""

    def __init__(self, user_id: str, *, embed_fn: Any = None, decision_model: Any = None) -> None:
        self.user_id = user_id
        self._embed_fn = embed_fn
        self._decision_model = decision_model

    async def _embed(self, content: str) -> list[float]:
        if self._embed_fn is not None:
            result = self._embed_fn(content)
            if asyncio.iscoroutine(result):
                result = await result
            return normalize_embedding(result)

        from app.core.models.llm import get_embeddings

        embeddings = get_embeddings()
        raw = await asyncio.to_thread(embeddings.embed_query, content)
        return normalize_embedding(raw)

    async def _decide(
        self, candidate: dict[str, Any], similar: list[dict[str, Any]]
    ) -> MemoryDecision:
        """Run the memory-write decision prompt; degrade to NOOP on any model failure.

        A failed/unavailable model must never crash the write path -- we
        fall back to treating the candidate as a duplicate of the closest
        match (the safest default: it avoids both silent data loss and
        uncontrolled note growth when the LLM is down).
        """
        best = similar[0]
        try:
            model = self._decision_model
            if model is None:
                from app.core.models.llm import get_fast_model

                model = get_fast_model()
            structured = model.with_structured_output(MemoryDecision)
            prompt = _load_decision_prompt().format(
                candidate=json.dumps(candidate),
                similar_notes=json.dumps(_summarize_similar(similar)),
            )
            decision = await asyncio.to_thread(structured.invoke, prompt)
            if not isinstance(decision, MemoryDecision):
                decision = MemoryDecision.model_validate(decision)
            return decision
        except Exception:
            logger.warning(
                "Memory-write decision model failed; defaulting to NOOP (reinforce closest match)",
                exc_info=True,
            )
            return MemoryDecision(
                decision="NOOP",
                note_id=best["id"],
                reason="decision model unavailable; defaulted to reinforcing the closest match",
            )

    async def consolidate(
        self,
        user_id: str,
        candidates: list[dict[str, Any]],
        source_episode_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Consolidate each candidate fact, returning a per-candidate result summary.

        Serialised per user (see ``_lock_for``) so concurrent turns for the same
        user can't race the read-decide-apply window into duplicate notes.
        """
        results = []
        async with _lock_for(user_id):
            for candidate in candidates:
                try:
                    result = await self._consolidate_one(user_id, candidate, source_episode_id)
                except Exception:
                    logger.warning(
                        "Failed to consolidate memory candidate %r", candidate, exc_info=True
                    )
                    result = {"action": "error", "note_id": None}
                results.append(result)
        return results

    async def _consolidate_one(
        self, user_id: str, candidate: dict[str, Any], source_episode_id: str | None
    ) -> dict[str, Any]:
        embedding = await self._embed(candidate["content"])
        similar = await notes_repo.search_similar_active_notes(
            user_id, embedding, limit=TOP_SIMILAR_FOR_DECISION
        )

        best_similarity = (
            l2_distance_to_cosine_similarity(similar[0]["distance"]) if similar else -1.0
        )
        if not similar or best_similarity < ADD_SIMILARITY_THRESHOLD:
            return await self._apply_add(user_id, candidate, embedding, source_episode_id)

        decision = await self._decide(candidate, similar)

        # Nova (and LLMs generally) sometimes return a note_id that isn't one of
        # the candidates we offered -- a hallucinated UUID, the note's *content*,
        # or None. Snap it back to a real candidate id so a target-referencing
        # decision can't silently drop the fact by raising downstream.
        valid_ids = {n["id"] for n in similar}
        target_id = decision.note_id if decision.note_id in valid_ids else None
        if target_id is None and decision.decision in ("UPDATE", "INVALIDATE", "NOOP"):
            if decision.decision == "INVALIDATE" and best_similarity < INVALIDATE_MIN_SIMILARITY:
                # No trustworthy note to contradict -- keep the fact rather than
                # inventing a contradiction against an unrelated note.
                return await self._apply_add(user_id, candidate, embedding, source_episode_id)
            target_id = similar[0]["id"]

        if decision.decision == "ADD":
            return await self._apply_add(user_id, candidate, embedding, source_episode_id)
        if decision.decision == "UPDATE":
            return await self._apply_update(
                user_id, candidate, embedding, target_id, decision.reason, source_episode_id
            )
        if decision.decision == "INVALIDATE":
            return await self._apply_invalidate(
                user_id, candidate, embedding, target_id, decision.reason, source_episode_id
            )
        return await self._apply_noop(target_id, decision.reason)

    async def _apply_add(
        self,
        user_id: str,
        candidate: dict[str, Any],
        embedding: list[float],
        source_episode_id: str | None,
    ) -> dict[str, Any]:
        note = await notes_repo.insert_note(
            user_id=user_id,
            content=candidate["content"],
            embedding=embedding,
            keywords=candidate.get("keywords") or [],
            tags=candidate.get("tags") or [],
            context=candidate.get("context"),
            importance=candidate.get("importance", 0.5),
            is_user_stated=candidate.get("is_user_stated", False),
            source_episode_id=source_episode_id,
            derived_from=[],
        )
        await audit.write_audit(
            None,
            user_id=user_id,
            actor=_ACTOR,
            action="add",
            target_table="memory_notes",
            target_id=note["id"],
            reason="new fact; no sufficiently similar existing note",
            details={"after": note},
        )
        await self._generate_links(user_id, note["id"], embedding)
        return {"action": "add", "note_id": note["id"]}

    async def _apply_update(
        self,
        user_id: str,
        candidate: dict[str, Any],
        embedding: list[float],
        target_id: str | None,
        reason: str,
        source_episode_id: str | None,
    ) -> dict[str, Any]:
        if target_id is None:
            raise ValueError("UPDATE decision requires a target note_id")
        old = await notes_repo.get_note(target_id)
        if old is None:
            raise ValueError(f"UPDATE target note not found: {target_id}")

        # Archive-old + insert-replacement is one atomic transaction (see
        # notes_repo.supersede_note) so a mid-sequence failure can't archive the
        # old note without a replacement existing.
        new_note = await notes_repo.supersede_note(
            target_id,
            old_status="archived",
            new_note={
                "user_id": user_id,
                "content": candidate["content"],
                "embedding": embedding,
                "keywords": candidate.get("keywords") or old["keywords"],
                "tags": candidate.get("tags") or old["tags"],
                "context": candidate.get("context") or old["context"],
                "importance": max(old["importance"], candidate.get("importance", 0.5)),
                "is_user_stated": candidate.get("is_user_stated", False),
                "source_episode_id": source_episode_id,
                "derived_from": [target_id],
            },
        )
        await audit.write_audit(
            None,
            user_id=user_id,
            actor=_ACTOR,
            action="update",
            target_table="memory_notes",
            target_id=new_note["id"],
            reason=reason,
            details={"before": old, "after": new_note},
        )
        await self._generate_links(user_id, new_note["id"], embedding)
        return {"action": "update", "note_id": new_note["id"], "superseded": target_id}

    async def _apply_invalidate(
        self,
        user_id: str,
        candidate: dict[str, Any],
        embedding: list[float],
        target_id: str | None,
        reason: str,
        source_episode_id: str | None,
    ) -> dict[str, Any]:
        if target_id is None:
            raise ValueError("INVALIDATE decision requires a target note_id")
        old = await notes_repo.get_note(target_id)
        if old is None:
            raise ValueError(f"INVALIDATE target note not found: {target_id}")

        # Invalidate-old + insert-replacement + contradicts-link is one atomic
        # transaction (see notes_repo.supersede_note): the "invalidate, don't
        # delete" record and its replacement can't end up half-written.
        new_note = await notes_repo.supersede_note(
            target_id,
            old_status="invalidated",
            new_note={
                "user_id": user_id,
                "content": candidate["content"],
                "embedding": embedding,
                "keywords": candidate.get("keywords") or [],
                "tags": candidate.get("tags") or [],
                "context": candidate.get("context"),
                "importance": candidate.get("importance", 0.5),
                "is_user_stated": candidate.get("is_user_stated", False),
                "source_episode_id": source_episode_id,
                "derived_from": [],
            },
            link_relation="contradicts",
            link_weight=1.0,
        )
        await audit.write_audit(
            None,
            user_id=user_id,
            actor=_ACTOR,
            action="invalidate",
            target_table="memory_notes",
            target_id=new_note["id"],
            reason=reason,
            details={"before": old, "after": new_note},
        )
        await self._generate_links(user_id, new_note["id"], embedding)
        return {"action": "invalidate", "note_id": new_note["id"], "invalidated": target_id}

    async def _apply_noop(self, target_id: str | None, reason: str) -> dict[str, Any]:
        if target_id is None:
            raise ValueError("NOOP decision requires a target note_id")
        old = await notes_repo.get_note(target_id)
        if old is None:
            raise ValueError(f"NOOP target note not found: {target_id}")

        new_strength = reinforce(old["strength"], old["access_count"])
        await notes_repo.reinforce_note(
            target_id, new_strength=new_strength, new_access_count=old["access_count"] + 1
        )
        await audit.write_audit(
            None,
            user_id=old["user_id"],
            actor=_ACTOR,
            action="read",
            target_table="memory_notes",
            target_id=target_id,
            reason=reason or "duplicate fact reinforced",
            details={},
        )
        return {"action": "noop", "note_id": target_id}

    async def _generate_links(self, user_id: str, note_id: str, embedding: list[float]) -> None:
        """Link ``note_id`` to up to ``MAX_LINKS_PER_NOTE`` similar active notes."""
        candidates = await notes_repo.search_similar_active_notes(
            user_id, embedding, limit=LINK_SEARCH_LIMIT
        )
        linked = 0
        for candidate in candidates:
            if linked >= MAX_LINKS_PER_NOTE:
                break
            if candidate["id"] == note_id:
                continue
            similarity = l2_distance_to_cosine_similarity(candidate["distance"])
            if similarity >= LINK_SIMILARITY_THRESHOLD:
                await notes_repo.insert_link(note_id, candidate["id"], "same_topic", similarity)
                linked += 1
