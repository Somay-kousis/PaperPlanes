"""Tests for app.memory.reflection: decay pass + reflection-insight synthesis.

No real DB/LLM: ``notes_repo``/``reflections_repo``/``audit`` are
monkeypatched with lightweight fakes (mirroring ``test_writer.py``'s
style); the "model" is a stand-in whose
``.with_structured_output(...).invoke(...)`` returns a canned
``ReflectionInsights`` (or raises, to exercise the degrade path).
Embeddings are supplied via the injectable ``embed_fn`` so no Titan/boto3
call ever happens.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.memory.reflection import (
    ReflectionInsight,
    ReflectionInsights,
    _decay_pass,
    _reflection_pass,
    run_reflection_cycle,
)

NOW = datetime.now(UTC)


def make_note(
    note_id: str,
    *,
    created_at: datetime | None = None,
    last_accessed_at: datetime | None = None,
    strength: float = 1.0,
    access_count: int = 0,
    importance: float = 0.5,
    content: str = "note content",
) -> dict[str, Any]:
    return {
        "id": note_id,
        "content": content,
        "importance": importance,
        "strength": strength,
        "last_accessed_at": last_accessed_at or NOW,
        "access_count": access_count,
        "created_at": created_at or (NOW - timedelta(days=10)),
    }


class FakeStructuredModel:
    """Stand-in for ``model.with_structured_output(ReflectionInsights)``."""

    def __init__(self, insights: ReflectionInsights | None = None, error: Exception | None = None):
        self._insights = insights
        self._error = error
        self.invoke_calls: list[str] = []

    def invoke(self, prompt: str) -> ReflectionInsights:
        self.invoke_calls.append(prompt)
        if self._error is not None:
            raise self._error
        return self._insights


class FakeModel:
    """Stand-in for ``get_fast_model()``: records with_structured_output calls."""

    def __init__(self, insights: ReflectionInsights | None = None, error: Exception | None = None):
        self.structured = FakeStructuredModel(insights=insights, error=error)
        self.with_structured_output_calls: list[Any] = []

    def with_structured_output(self, schema: Any) -> FakeStructuredModel:
        self.with_structured_output_calls.append(schema)
        return self.structured


class NotesRepoFake:
    def __init__(self, notes: list[dict[str, Any]]):
        self.notes = notes
        self.archived: list[str] = []

    async def list_notes(self, user_id: str, *, status: str = "active", limit: int = 500):
        return list(self.notes)

    async def archive_note(self, note_id: str) -> None:
        self.archived.append(note_id)


class ReflectionsRepoFake:
    def __init__(self, existing: list[dict[str, Any]] | None = None):
        self.existing = existing or []
        self.inserted: list[dict[str, Any]] = []
        self._counter = 0

    async def list_reflections(self, user_id: str, *, limit: int = 1):
        return self.existing[:limit]

    async def insert_reflection(self, **kwargs: Any) -> dict[str, Any]:
        self._counter += 1
        row = {"id": f"reflection-{self._counter}", **kwargs}
        self.inserted.append(row)
        return row


class AuditFake:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def write_audit(self, conn_or_session=None, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "audit-1"


def wire(
    monkeypatch,
    notes_repo_fake: NotesRepoFake,
    reflections_repo_fake: ReflectionsRepoFake,
    audit_fake: AuditFake,
) -> None:
    from app.memory import audit
    from app.memory.db import notes_repo, reflections_repo

    monkeypatch.setattr(notes_repo, "list_notes", notes_repo_fake.list_notes)
    monkeypatch.setattr(notes_repo, "archive_note", notes_repo_fake.archive_note)
    monkeypatch.setattr(
        reflections_repo, "list_reflections", reflections_repo_fake.list_reflections
    )
    monkeypatch.setattr(
        reflections_repo, "insert_reflection", reflections_repo_fake.insert_reflection
    )
    monkeypatch.setattr(audit, "write_audit", audit_fake.write_audit)


async def _embed_fn(text: str) -> list[float]:
    return [1.0, 0.0, 0.0]


# --------------------------------------------------------------------------
# Decay pass
# --------------------------------------------------------------------------


async def test_decay_pass_archives_only_stale_old_low_access_notes(monkeypatch):
    stale_old = make_note(
        "stale-old",
        created_at=NOW - timedelta(days=10),
        last_accessed_at=NOW - timedelta(days=10),
        strength=0.5,
        access_count=0,
    )  # dt ~ 10 days, strength 0.5 -> retention ~ 0, well below threshold
    too_fresh = make_note(
        "too-fresh",
        created_at=NOW - timedelta(hours=1),
        last_accessed_at=NOW - timedelta(hours=1),
        strength=0.01,
        access_count=0,
    )  # would decay hard, but too new -- protected by DECAY_MIN_AGE
    well_reinforced = make_note(
        "well-reinforced",
        created_at=NOW - timedelta(days=10),
        last_accessed_at=NOW - timedelta(days=10),
        strength=0.01,
        access_count=5,
    )  # would decay hard, but accessed often -- protected
    strong = make_note(
        "strong",
        created_at=NOW - timedelta(days=10),
        last_accessed_at=NOW - timedelta(days=10),
        strength=1_000_000.0,
        access_count=0,
    )  # barely decays -- retention stays well above threshold

    notes_repo_fake = NotesRepoFake([stale_old, too_fresh, well_reinforced, strong])
    reflections_repo_fake = ReflectionsRepoFake()
    audit_fake = AuditFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, audit_fake)

    archived = await _decay_pass("user-1", now=NOW)

    assert archived == 1
    assert notes_repo_fake.archived == ["stale-old"]
    assert audit_fake.calls[0]["action"] == "archive"
    assert audit_fake.calls[0]["target_id"] == "stale-old"
    assert audit_fake.calls[0]["target_table"] == "memory_notes"


async def test_decay_pass_returns_zero_when_notes_repo_fails(monkeypatch):
    notes_repo_fake = NotesRepoFake([])

    async def boom(user_id, *, status="active", limit=500):
        raise RuntimeError("db down")

    monkeypatch.setattr(notes_repo_fake, "list_notes", boom)
    wire(monkeypatch, notes_repo_fake, ReflectionsRepoFake(), AuditFake())

    archived = await _decay_pass("user-1", now=NOW)

    assert archived == 0


# --------------------------------------------------------------------------
# Reflection pass: importance gate
# --------------------------------------------------------------------------


async def test_reflection_pass_gate_skips_scheduled_trigger_below_threshold(monkeypatch):
    notes = [make_note(f"n{i}", importance=0.2) for i in range(3)]  # sum = 0.6, well under gate
    notes_repo_fake = NotesRepoFake(notes)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    model = FakeModel()

    created = await _reflection_pass(
        "user-1", now=NOW, trigger_reason="scheduled", embed_fn=_embed_fn, decision_model=model
    )

    assert created == 0
    assert model.with_structured_output_calls == []
    assert reflections_repo_fake.inserted == []


async def test_reflection_pass_manual_trigger_bypasses_gate(monkeypatch):
    notes = [make_note(f"n{i}", importance=0.2) for i in range(3)]  # same low-importance pool
    notes_repo_fake = NotesRepoFake(notes)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    insights = ReflectionInsights(
        insights=[ReflectionInsight(content="an insight", cites=["n0"])]
    )
    model = FakeModel(insights=insights)

    created = await _reflection_pass(
        "user-1", now=NOW, trigger_reason="manual", embed_fn=_embed_fn, decision_model=model
    )

    assert created == 1
    assert model.with_structured_output_calls == [ReflectionInsights]


# --------------------------------------------------------------------------
# Reflection pass: citation validation
# --------------------------------------------------------------------------


async def test_reflection_pass_drops_hallucinated_cites_keeps_valid_ones(monkeypatch):
    notes = [make_note("n1", importance=0.9), make_note("n2", importance=0.9)]
    notes_repo_fake = NotesRepoFake(notes)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    insights = ReflectionInsights(
        insights=[
            # Partially hallucinated: kept, but the fake id is stripped out.
            ReflectionInsight(content="insight A", cites=["n1", "not-a-real-id"]),
            # Fully hallucinated: no valid citation survives -- dropped entirely.
            ReflectionInsight(content="insight B", cites=["fake-1", "fake-2"]),
        ]
    )
    model = FakeModel(insights=insights)

    created = await _reflection_pass(
        "user-1", now=NOW, trigger_reason="manual", embed_fn=_embed_fn, decision_model=model
    )

    assert created == 1
    assert len(reflections_repo_fake.inserted) == 1
    assert reflections_repo_fake.inserted[0]["cites"] == ["n1"]
    assert reflections_repo_fake.inserted[0]["content"] == "insight A"


async def test_reflection_pass_importance_averages_cited_notes(monkeypatch):
    notes = [make_note("n1", importance=0.4), make_note("n2", importance=0.8)]
    notes_repo_fake = NotesRepoFake(notes)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    insights = ReflectionInsights(
        insights=[ReflectionInsight(content="insight", cites=["n1", "n2"])]
    )
    model = FakeModel(insights=insights)

    await _reflection_pass(
        "user-1", now=NOW, trigger_reason="manual", embed_fn=_embed_fn, decision_model=model
    )

    assert reflections_repo_fake.inserted[0]["importance"] == pytest.approx(0.6)  # (0.4 + 0.8) / 2


async def test_reflection_pass_caps_at_max_insights(monkeypatch):
    notes = [make_note("n1", importance=0.9)]
    notes_repo_fake = NotesRepoFake(notes)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    insights = ReflectionInsights(
        insights=[ReflectionInsight(content=f"insight {i}", cites=["n1"]) for i in range(5)]
    )
    model = FakeModel(insights=insights)

    created = await _reflection_pass(
        "user-1", now=NOW, trigger_reason="manual", embed_fn=_embed_fn, decision_model=model
    )

    assert created == 3  # MAX_INSIGHTS


# --------------------------------------------------------------------------
# Reflection pass: model failure
# --------------------------------------------------------------------------


async def test_reflection_pass_model_error_returns_zero(monkeypatch):
    notes = [make_note("n1", importance=0.9)]
    notes_repo_fake = NotesRepoFake(notes)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    model = FakeModel(error=RuntimeError("bedrock unavailable"))

    created = await _reflection_pass(
        "user-1", now=NOW, trigger_reason="manual", embed_fn=_embed_fn, decision_model=model
    )

    assert created == 0
    assert reflections_repo_fake.inserted == []


# --------------------------------------------------------------------------
# Full cycle: run_reflection_cycle never raises, counts are correct
# --------------------------------------------------------------------------


async def test_run_reflection_cycle_model_error_degrades_to_decay_only(monkeypatch):
    stale_old = make_note(
        "stale-old",
        created_at=NOW - timedelta(days=10),
        last_accessed_at=NOW - timedelta(days=10),
        strength=0.5,
        access_count=0,
        importance=0.9,
    )
    notes_repo_fake = NotesRepoFake([stale_old])
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    model = FakeModel(error=RuntimeError("bedrock unavailable"))

    result = await run_reflection_cycle(
        "user-1", trigger_reason="manual", now=NOW, embed_fn=_embed_fn, decision_model=model
    )

    assert result == {"reflections_created": 0, "notes_archived": 1, "contradictions_found": 0}


async def test_run_reflection_cycle_full_success_counts_correct(monkeypatch):
    stale_old = make_note(
        "stale-old",
        created_at=NOW - timedelta(days=10),
        last_accessed_at=NOW - timedelta(days=10),
        strength=0.5,
        access_count=0,
        importance=0.9,
    )
    important_note = make_note("n1", importance=0.9)
    notes_repo_fake = NotesRepoFake([stale_old, important_note])
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())
    insights = ReflectionInsights(
        insights=[ReflectionInsight(content="an insight", cites=["n1"])]
    )
    model = FakeModel(insights=insights)

    result = await run_reflection_cycle(
        "user-1", trigger_reason="manual", now=NOW, embed_fn=_embed_fn, decision_model=model
    )

    assert result == {"reflections_created": 1, "notes_archived": 1, "contradictions_found": 0}


async def test_run_reflection_cycle_never_raises_when_everything_fails(monkeypatch):
    notes_repo_fake = NotesRepoFake([])

    async def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(notes_repo_fake, "list_notes", boom)
    reflections_repo_fake = ReflectionsRepoFake()
    wire(monkeypatch, notes_repo_fake, reflections_repo_fake, AuditFake())

    result = await run_reflection_cycle("user-1", trigger_reason="manual", now=NOW)

    assert result == {"reflections_created": 0, "notes_archived": 0, "contradictions_found": 0}
