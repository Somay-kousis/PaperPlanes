"""Tests for app.memory.writer.MemoryWriter: dedupe/decide/apply + audit wiring.

No real DB/LLM: ``notes_repo``/``audit`` are monkeypatched with AsyncMocks
(mirroring ``test_chunks_repo``'s DB-free style) and the decision "model" is
a stand-in object whose ``.with_structured_output(...).invoke(...)`` returns
a canned ``MemoryDecision`` (or raises, to exercise the fallback path).
Embeddings are supplied via the injectable ``embed_fn`` so no Titan/boto3
call ever happens.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.memory.writer import MemoryDecision, MemoryWriter

NOW = datetime.now(UTC)


def make_note(note_id: str = "note-1", **overrides: Any) -> dict[str, Any]:
    note = {
        "id": note_id,
        "user_id": "user-1",
        "content": "old content",
        "keywords": ["k1"],
        "tags": ["t1"],
        "context": "ctx",
        "importance": 0.5,
        "strength": 1.0,
        "last_accessed_at": NOW,
        "access_count": 0,
        "confidence": 0.7,
        "is_user_stated": False,
        "source_episode_id": None,
        "derived_from": [],
        "status": "active",
        "valid_at": NOW,
        "invalid_at": None,
        "created_at": NOW,
        "expired_at": None,
    }
    note.update(overrides)
    return note


def make_similar(note_id: str = "note-1", distance: float = 0.5, **overrides: Any) -> dict:
    """A similar-note row as returned by search_similar_active_notes (has 'distance')."""
    note = make_note(note_id, **overrides)
    note["distance"] = distance
    return note


class FakeStructuredModel:
    """Stand-in for ``model.with_structured_output(MemoryDecision)``."""

    def __init__(self, decision: MemoryDecision | None = None, error: Exception | None = None):
        self._decision = decision
        self._error = error
        self.invoke_calls: list[str] = []

    def invoke(self, prompt: str) -> MemoryDecision:
        self.invoke_calls.append(prompt)
        if self._error is not None:
            raise self._error
        return self._decision


class FakeDecisionModel:
    """Stand-in for ``get_fast_model()``: records with_structured_output calls."""

    def __init__(self, decision: MemoryDecision | None = None, error: Exception | None = None):
        self.structured = FakeStructuredModel(decision=decision, error=error)
        self.with_structured_output_calls: list[Any] = []

    def with_structured_output(self, schema: Any) -> FakeStructuredModel:
        self.with_structured_output_calls.append(schema)
        return self.structured


class Repo:
    """Records calls made to the mocked notes_repo/audit boundary."""

    def __init__(self):
        self.inserted: list[dict[str, Any]] = []
        self.archived: list[str] = []
        self.invalidated: list[str] = []
        self.reinforced: list[tuple[str, float, int]] = []
        self.links: list[tuple[str, str, str, float]] = []
        self.audits: list[dict[str, Any]] = []
        self.notes_by_id: dict[str, dict[str, Any]] = {}
        self._insert_counter = 0

    def register(self, note: dict[str, Any]) -> None:
        self.notes_by_id[note["id"]] = note

    async def insert_note(self, **kwargs: Any) -> dict[str, Any]:
        self._insert_counter += 1
        new_id = f"new-note-{self._insert_counter}"
        note = make_note(
            new_id,
            content=kwargs["content"],
            keywords=kwargs.get("keywords") or [],
            tags=kwargs.get("tags") or [],
            context=kwargs.get("context"),
            importance=kwargs.get("importance", 0.5),
            is_user_stated=kwargs.get("is_user_stated", False),
            derived_from=kwargs.get("derived_from") or [],
            user_id=kwargs["user_id"],
        )
        self.inserted.append({**kwargs, "id": new_id})
        self.notes_by_id[new_id] = note
        return note

    async def get_note(self, note_id: str) -> dict[str, Any] | None:
        return self.notes_by_id.get(note_id)

    async def archive_note(self, note_id: str) -> None:
        self.archived.append(note_id)

    async def invalidate_note(self, note_id: str) -> None:
        self.invalidated.append(note_id)

    async def supersede_note(
        self, old_note_id: str, *, old_status: str, new_note: dict[str, Any],
        link_relation: str | None = None, link_weight: float = 1.0,
    ) -> dict[str, Any]:
        # Mirrors the real atomic supersede: mark old, insert new, optional link.
        (self.archived if old_status == "archived" else self.invalidated).append(old_note_id)
        note = await self.insert_note(**new_note)
        if link_relation:
            self.links.append((note["id"], old_note_id, link_relation, link_weight))
        return note

    async def reinforce_note(self, note_id: str, *, new_strength: float, new_access_count: int):
        self.reinforced.append((note_id, new_strength, new_access_count))

    async def insert_link(self, source: str, target: str, relation_type: str, weight: float):
        self.links.append((source, target, relation_type, weight))
        return "link-1"

    async def write_audit(self, conn_or_session=None, **kwargs: Any):
        self.audits.append(kwargs)
        return "audit-1"


def wire_repo(monkeypatch: pytest.MonkeyPatch, repo: Repo, *, search_results: list) -> None:
    """Patch notes_repo/audit module functions, and search results (as a queue)."""
    from app.memory import audit
    from app.memory.db import notes_repo

    search_queue = list(search_results)

    async def fake_search(user_id, embedding, *, limit=5):
        if search_queue:
            return search_queue.pop(0)
        return []

    monkeypatch.setattr(notes_repo, "search_similar_active_notes", fake_search)
    monkeypatch.setattr(notes_repo, "insert_note", repo.insert_note)
    monkeypatch.setattr(notes_repo, "get_note", repo.get_note)
    monkeypatch.setattr(notes_repo, "archive_note", repo.archive_note)
    monkeypatch.setattr(notes_repo, "invalidate_note", repo.invalidate_note)
    monkeypatch.setattr(notes_repo, "supersede_note", repo.supersede_note)
    monkeypatch.setattr(notes_repo, "reinforce_note", repo.reinforce_note)
    monkeypatch.setattr(notes_repo, "insert_link", repo.insert_link)
    monkeypatch.setattr(audit, "write_audit", repo.write_audit)


async def _embed_fn(text: str) -> list[float]:
    return [1.0, 0.0, 0.0]


CANDIDATE = {"content": "the sky is blue", "importance": 0.6, "is_user_stated": True}


# --------------------------------------------------------------------------
# Auto-ADD path (no LLM call)
# --------------------------------------------------------------------------


async def test_auto_add_when_no_similar_notes(monkeypatch):
    repo = Repo()
    wire_repo(monkeypatch, repo, search_results=[[], []])
    decision_model = FakeDecisionModel()
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=decision_model)

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result == {"action": "add", "note_id": repo.inserted[0]["id"]}
    assert repo.audits[0]["action"] == "add"
    assert decision_model.with_structured_output_calls == []


async def test_auto_add_when_best_similarity_below_threshold(monkeypatch):
    repo = Repo()
    # distance=1.5 -> cosine similarity = 1 - 1.5^2/2 = -0.125, well below 0.60.
    low_sim = make_similar("note-1", distance=1.5)
    wire_repo(monkeypatch, repo, search_results=[[low_sim], []])
    decision_model = FakeDecisionModel()
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=decision_model)

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result["action"] == "add"
    assert decision_model.with_structured_output_calls == []


# --------------------------------------------------------------------------
# The 4 decision branches (similarity clears ADD_SIMILARITY_THRESHOLD)
# --------------------------------------------------------------------------


async def test_decision_add_branch(monkeypatch):
    repo = Repo()
    similar = make_similar("note-1", distance=0.5)  # similarity 0.875
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    decision = MemoryDecision(decision="ADD", note_id=None, reason="actually new")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result == {"action": "add", "note_id": repo.inserted[0]["id"]}
    assert repo.audits[0]["action"] == "add"


async def test_decision_update_branch(monkeypatch):
    repo = Repo()
    old = make_note("note-1", importance=0.3)
    repo.register(old)
    similar = make_similar("note-1", distance=0.5, importance=0.3)
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    decision = MemoryDecision(decision="UPDATE", note_id="note-1", reason="refined fact")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert repo.archived == ["note-1"]
    new_id = repo.inserted[0]["id"]
    assert repo.inserted[0]["derived_from"] == ["note-1"]
    # importance = max(old, new) = max(0.3, 0.6) = 0.6
    assert repo.inserted[0]["importance"] == 0.6
    assert result == {"action": "update", "note_id": new_id, "superseded": "note-1"}
    audit_row = repo.audits[0]
    assert audit_row["action"] == "update"
    assert audit_row["details"]["before"]["id"] == "note-1"
    assert audit_row["details"]["after"]["id"] == new_id


async def test_decision_invalidate_branch(monkeypatch):
    repo = Repo()
    old = make_note("note-1")
    repo.register(old)
    similar = make_similar("note-1", distance=0.5)
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    decision = MemoryDecision(decision="INVALIDATE", note_id="note-1", reason="contradicted")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert repo.invalidated == ["note-1"]
    new_id = repo.inserted[0]["id"]
    assert repo.links == [(new_id, "note-1", "contradicts", 1.0)]
    assert result == {"action": "invalidate", "note_id": new_id, "invalidated": "note-1"}
    audit_row = repo.audits[0]
    assert audit_row["action"] == "invalidate"
    assert audit_row["details"]["before"]["id"] == "note-1"


async def test_decision_noop_branch(monkeypatch):
    repo = Repo()
    old = make_note("note-1", strength=1.0, access_count=0)
    repo.register(old)
    similar = make_similar("note-1", distance=0.5)
    wire_repo(monkeypatch, repo, search_results=[[similar]])
    decision = MemoryDecision(decision="NOOP", note_id="note-1", reason="duplicate")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result == {"action": "noop", "note_id": "note-1"}
    assert repo.reinforced == [("note-1", pytest.approx(2.0), 1)]
    assert repo.audits[0]["action"] == "read"
    # NOOP never inserts a new note or archives/invalidates anything.
    assert repo.inserted == []
    assert repo.archived == []
    assert repo.invalidated == []


# --------------------------------------------------------------------------
# note_id coercion
# --------------------------------------------------------------------------


async def test_note_id_coercion_snaps_update_to_closest_candidate(monkeypatch):
    repo = Repo()
    old = make_note("note-1")
    repo.register(old)
    similar = make_similar("note-1", distance=0.5)
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    # Hallucinated id not present in the candidate set.
    decision = MemoryDecision(decision="UPDATE", note_id="not-a-real-id", reason="refine")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result["action"] == "update"
    assert result["superseded"] == "note-1"
    assert repo.archived == ["note-1"]


async def test_note_id_coercion_snaps_noop_to_closest_candidate(monkeypatch):
    repo = Repo()
    old = make_note("note-1")
    repo.register(old)
    similar = make_similar("note-1", distance=0.5)
    wire_repo(monkeypatch, repo, search_results=[[similar]])
    decision = MemoryDecision(decision="NOOP", note_id=None, reason="dup")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result == {"action": "noop", "note_id": "note-1"}


async def test_note_id_coercion_invalidate_snaps_to_closest_when_similarity_sufficient(
    monkeypatch,
):
    repo = Repo()
    old = make_note("note-1")
    repo.register(old)
    similar = make_similar("note-1", distance=0.5)  # sim 0.875, clears both thresholds
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    decision = MemoryDecision(decision="INVALIDATE", note_id="hallucinated-id", reason="???")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    # Similarity (0.875) is >= INVALIDATE_MIN_SIMILARITY (0.60), so the target
    # snaps to similar[0]["id"] rather than downgrading to ADD.
    assert result["action"] == "invalidate"
    assert result["invalidated"] == "note-1"


async def test_note_id_coercion_invalidate_downgrades_to_add_when_target_untrustworthy(
    monkeypatch,
):
    repo = Repo()
    # Use two search calls: the decision-time search returns a note whose
    # similarity clears ADD_SIMILARITY_THRESHOLD only barely so we can craft a
    # case where the *coercion* branch's own guard (best_similarity <
    # INVALIDATE_MIN_SIMILARITY) fires. Since both thresholds are numerically
    # equal (0.60), we monkeypatch INVALIDATE_MIN_SIMILARITY higher for this
    # test to exercise the downgrade path in isolation.
    from app.memory import writer as writer_module

    monkeypatch.setattr(writer_module, "INVALIDATE_MIN_SIMILARITY", 0.95)
    similar = make_similar("note-1", distance=0.5)  # similarity 0.875 < 0.95
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    decision = MemoryDecision(decision="INVALIDATE", note_id="hallucinated-id", reason="???")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result["action"] == "add"
    assert repo.invalidated == []


# --------------------------------------------------------------------------
# Decision-model failure -> NOOP fallback
# --------------------------------------------------------------------------


async def test_decision_model_error_falls_back_to_noop(monkeypatch):
    repo = Repo()
    old = make_note("note-1", strength=1.0, access_count=0)
    repo.register(old)
    similar = make_similar("note-1", distance=0.5)
    wire_repo(monkeypatch, repo, search_results=[[similar]])
    decision_model = FakeDecisionModel(error=RuntimeError("bedrock unavailable"))
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=decision_model)

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    assert result == {"action": "noop", "note_id": "note-1"}
    assert repo.reinforced
    assert repo.audits[0]["action"] == "read"


# --------------------------------------------------------------------------
# consolidate(): per-candidate error isolation
# --------------------------------------------------------------------------


async def test_consolidate_wraps_per_candidate_errors(monkeypatch):
    repo = Repo()
    wire_repo(monkeypatch, repo, search_results=[[], []])
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel())

    async def boom(user_id, candidate, source_episode_id):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(writer, "_consolidate_one", boom)

    results = await writer.consolidate("user-1", [CANDIDATE, CANDIDATE], None)

    assert results == [
        {"action": "error", "note_id": None},
        {"action": "error", "note_id": None},
    ]


async def test_consolidate_continues_after_one_candidate_errors(monkeypatch):
    repo = Repo()
    wire_repo(monkeypatch, repo, search_results=[[], [], [], []])
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel())

    calls = {"n": 0}
    original = writer._consolidate_one

    async def flaky(user_id, candidate, source_episode_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first one fails")
        return await original(user_id, candidate, source_episode_id)

    monkeypatch.setattr(writer, "_consolidate_one", flaky)

    results = await writer.consolidate("user-1", [CANDIDATE, CANDIDATE], None)

    assert results[0] == {"action": "error", "note_id": None}
    assert results[1]["action"] == "add"


# --------------------------------------------------------------------------
# Link generation
# --------------------------------------------------------------------------


async def test_generate_links_creates_link_above_threshold(monkeypatch):
    repo = Repo()
    # First search (dedupe gate): nothing similar enough -> auto ADD.
    # Second search (link generation): one note above LINK_SIMILARITY_THRESHOLD (0.75).
    link_candidate = make_similar("other-note", distance=0.3)  # sim = 1 - 0.045 = 0.955
    wire_repo(monkeypatch, repo, search_results=[[], [link_candidate]])
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel())

    result = await writer._consolidate_one("user-1", CANDIDATE, None)

    new_id = repo.inserted[0]["id"]
    assert repo.links == [(new_id, "other-note", "same_topic", pytest.approx(0.955, abs=1e-3))]
    assert result["action"] == "add"


async def test_generate_links_skips_self_and_below_threshold(monkeypatch):
    repo = Repo()
    low_sim_other = make_similar("other-note", distance=1.2)  # sim well below 0.75
    wire_repo(monkeypatch, repo, search_results=[[], [low_sim_other]])
    writer = MemoryWriter("user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel())

    await writer._consolidate_one("user-1", CANDIDATE, None)

    assert repo.links == []


# --------------------------------------------------------------------------
# Missing target -> raised, caught by consolidate() as an "error" result
# --------------------------------------------------------------------------


async def test_update_target_not_found_is_reported_as_error_via_consolidate(monkeypatch):
    repo = Repo()  # note-1 is never registered -> get_note returns None
    similar = make_similar("note-1", distance=0.5)
    wire_repo(monkeypatch, repo, search_results=[[similar], []])
    decision = MemoryDecision(decision="UPDATE", note_id="note-1", reason="refine")
    writer = MemoryWriter(
        "user-1", embed_fn=_embed_fn, decision_model=FakeDecisionModel(decision=decision)
    )

    results = await writer.consolidate("user-1", [CANDIDATE], None)

    assert results == [{"action": "error", "note_id": None}]
