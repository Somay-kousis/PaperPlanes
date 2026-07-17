"""MemoryEngine: the facade the chat/ingestion graphs talk to.

Wraps the retrieval (``retriever``), writing (``writer``), and audit
(``audit``) subsystems behind a single interface so callers that don't
need per-row DB details can go through one object. The chat graph itself
calls ``retriever``/``writer`` directly (via ``retrieve_node``/
``extract_facts_node``/``memory_write_node``) for finer-grained control
over state; this facade is the simpler surface for one-off callers (e.g.
scripts, future tool-use surfaces).
"""

from typing import Any

from app.memory import audit
from app.memory.db import notes_repo
from app.memory.retriever import retrieve_and_reinforce
from app.memory.writer import MemoryWriter


class MemoryEngine:
    """Facade over the CockroachDB-backed memory subsystem."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    async def retrieve(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve the top-``limit`` memory notes relevant to ``query``."""
        return await retrieve_and_reinforce(self.user_id, query, top_k=limit)

    async def write(self, content: str, *, is_user_stated: bool = False, **kwargs: Any) -> str:
        """Write (or consolidate) a memory note, returning its id.

        Runs the full ``MemoryWriter.consolidate`` dedup/decision pipeline
        for a single candidate fact -- see ``app.memory.writer`` for the
        ADD/UPDATE/INVALIDATE/NOOP semantics.
        """
        source_episode_id = kwargs.pop("source_episode_id", None)
        candidate = {"content": content, "is_user_stated": is_user_stated, **kwargs}
        writer = MemoryWriter(self.user_id)
        results = await writer.consolidate(self.user_id, [candidate], source_episode_id)
        return results[0]["note_id"]

    async def invalidate(self, note_id: str, *, reason: str) -> None:
        """Mark a memory note as invalid/superseded, writing an audit row."""
        note = await notes_repo.get_note(note_id)
        await notes_repo.invalidate_note(note_id)
        await audit.write_audit(
            None,
            user_id=note["user_id"] if note else self.user_id,
            actor="system:memory_engine",
            action="invalidate",
            target_table="memory_notes",
            target_id=note_id,
            reason=reason,
            details={"before": note} if note else {},
        )

    async def reflect(self) -> list[str]:
        """Generate reflections over recent memory, returning new reflection ids.

        Not implemented in Week 2 -- driven by ``workers.reflection_worker``
        on a schedule in a later week; uses ``reflection.md`` against a
        window of recent notes/episodes.
        """
        raise NotImplementedError
