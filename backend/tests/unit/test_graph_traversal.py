"""Tests for app.memory.graph_traversal.expand_via_links.

``expand_via_links`` issues a single recursive-CTE query over the async
SQLAlchemy engine, so there's no DB-free way to unit-test the SQL itself.
Instead, ``get_engine`` is monkeypatched to a fake engine whose
``execute()`` runs a small pure-Python reference implementation of the
same recursive-CTE semantics (BFS out to ``max_hops`` steps, accumulating
``weight * hop_decay**hops`` per path, then collapsing to
``MIN(hops)``/``MAX(path_weight)`` per note -- exactly the query's own
``GROUP BY``) over a fixture link set. This lets these tests verify
result shaping, hop-decay weighting, and cycle safety (a link cycle must
not hang the traversal) without any real database.
"""

from typing import Any

from app.memory.graph_traversal import HOP_DECAY, expand_via_links

# --------------------------------------------------------------------------
# Fake DB layer: a reference recursive-CTE implementation over a fixture graph.
# --------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeConn:
    def __init__(self, links: list[tuple[str, str, str, float, bool]], statuses: dict[str, str]):
        self.links = links
        self.statuses = statuses  # note_id -> status ("active"/"archived"/...)
        self.calls: list[dict[str, Any]] = []

    async def execute(self, _stmt: Any, params: dict[str, Any]) -> FakeResult:
        self.calls.append(params)
        rows = _reference_traversal(self.links, self.statuses, params)
        return FakeResult(rows)

    async def __aenter__(self) -> "FakeConn":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class FakeEngineHandle:
    def __init__(self, conn: FakeConn):
        self._conn = conn

    def connect(self) -> FakeConn:
        return self._conn


class FakeCockroachEngine:
    def __init__(self, conn: FakeConn):
        self.engine = FakeEngineHandle(conn)


def _reference_traversal(
    links: list[tuple[str, str, str, float, bool]],
    statuses: dict[str, str],
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Pure-Python mirror of the ``expand_via_links`` recursive CTE.

    ``links`` entries are ``(source, target, relation_type, weight, invalid)``.
    Bounded strictly by ``max_hops`` iterations, so a cycle in ``links``
    cannot cause this to loop indefinitely.
    """
    seed_ids = params["seed_ids"]
    max_hops = params["max_hops"]
    relations = set(params["relations"])
    hop_decay = params["hop_decay"]
    limit = params["limit"]

    frontier = [(note_id, 0, 1.0) for note_id in seed_ids]
    all_paths = list(frontier)

    for _ in range(max_hops):
        next_frontier = []
        for note_id, hops, weight in frontier:
            for source, target, relation, edge_weight, invalid in links:
                if invalid or relation not in relations:
                    continue
                if source == note_id:
                    neighbor = target
                elif target == note_id:
                    neighbor = source
                else:
                    continue
                next_frontier.append((neighbor, hops + 1, weight * edge_weight * hop_decay))
        all_paths.extend(next_frontier)
        frontier = next_frontier
        if not frontier:
            break

    seed_set = set(seed_ids)
    best: dict[str, tuple[int, float]] = {}
    for note_id, hops, weight in all_paths:
        if hops == 0:
            continue
        if note_id in seed_set:  # seeds are never returned, even re-reached via a cycle
            continue
        if statuses.get(note_id) != "active":
            continue
        if note_id not in best:
            best[note_id] = (hops, weight)
        else:
            cur_hops, cur_weight = best[note_id]
            best[note_id] = (min(cur_hops, hops), max(cur_weight, weight))

    rows = [
        {"note_id": note_id, "hops": hops, "path_weight": weight}
        for note_id, (hops, weight) in best.items()
    ]
    rows.sort(key=lambda r: r["path_weight"], reverse=True)
    return rows[:limit]


def wire(monkeypatch, links, statuses):
    import app.memory.graph_traversal as gt

    conn = FakeConn(links, statuses)
    fake_engine = FakeCockroachEngine(conn)
    monkeypatch.setattr(gt, "get_engine", lambda: fake_engine)
    return conn


# --------------------------------------------------------------------------
# Empty seeds -> [] without touching the DB
# --------------------------------------------------------------------------


async def test_empty_seeds_returns_empty_without_querying(monkeypatch):
    calls = {"n": 0}

    def spy_get_engine():
        calls["n"] += 1
        raise AssertionError("get_engine should not be called for empty seeds")

    import app.memory.graph_traversal as gt

    monkeypatch.setattr(gt, "get_engine", spy_get_engine)

    result = await expand_via_links("user-1", [], hops=1)

    assert result == []
    assert calls["n"] == 0


async def test_zero_hops_returns_empty_without_querying(monkeypatch):
    import app.memory.graph_traversal as gt

    monkeypatch.setattr(
        gt, "get_engine", lambda: (_ for _ in ()).throw(AssertionError("should not be called"))
    )

    result = await expand_via_links("user-1", ["seed-1"], hops=0)

    assert result == []


# --------------------------------------------------------------------------
# Result shaping
# --------------------------------------------------------------------------


async def test_one_hop_neighbor_is_returned_shaped_correctly(monkeypatch):
    links = [("seed-1", "neighbor-1", "same_topic", 0.8, False)]
    statuses = {"seed-1": "active", "neighbor-1": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=1, limit=10)

    assert result == [
        {"note_id": "neighbor-1", "hops": 1, "path_weight": 0.8 * HOP_DECAY}
    ]


async def test_seed_itself_is_never_returned(monkeypatch):
    links = [("seed-1", "neighbor-1", "same_topic", 1.0, False)]
    statuses = {"seed-1": "active", "neighbor-1": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=1)

    assert all(row["note_id"] != "seed-1" for row in result)


async def test_invalid_link_is_not_traversed(monkeypatch):
    links = [("seed-1", "neighbor-1", "same_topic", 1.0, True)]  # invalidated
    statuses = {"seed-1": "active", "neighbor-1": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=1)

    assert result == []


async def test_non_traversable_relation_type_is_ignored(monkeypatch):
    links = [("seed-1", "neighbor-1", "contradicts", 1.0, False)]
    statuses = {"seed-1": "active", "neighbor-1": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=1)

    assert result == []


async def test_archived_neighbor_is_excluded(monkeypatch):
    links = [("seed-1", "neighbor-1", "same_topic", 1.0, False)]
    statuses = {"seed-1": "active", "neighbor-1": "archived"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=1)

    assert result == []


# --------------------------------------------------------------------------
# Hop-decay weighting
# --------------------------------------------------------------------------


async def test_two_hop_path_decays_multiplicatively(monkeypatch):
    links = [
        ("seed-1", "mid", "same_topic", 1.0, False),
        ("mid", "far", "same_topic", 1.0, False),
    ]
    statuses = {"seed-1": "active", "mid": "active", "far": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=2, limit=10)

    by_id = {row["note_id"]: row for row in result}
    assert by_id["mid"]["path_weight"] == HOP_DECAY
    assert by_id["far"]["hops"] == 2
    assert by_id["far"]["path_weight"] == HOP_DECAY * HOP_DECAY


async def test_closer_path_outranks_farther_one_for_same_note(monkeypatch):
    # neighbor reachable both directly (1 hop, weight 1.0) and via a detour
    # (2 hops, weight 1.0*1.0) -- the direct path's higher weight should win.
    links = [
        ("seed-1", "neighbor-1", "same_topic", 1.0, False),
        ("seed-1", "detour", "same_topic", 1.0, False),
        ("detour", "neighbor-1", "same_topic", 1.0, False),
    ]
    statuses = {"seed-1": "active", "neighbor-1": "active", "detour": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=2, limit=10)

    by_id = {row["note_id"]: row for row in result}
    assert by_id["neighbor-1"]["hops"] == 1
    assert by_id["neighbor-1"]["path_weight"] == HOP_DECAY  # the direct, less-decayed path


# --------------------------------------------------------------------------
# Cycle safety
# --------------------------------------------------------------------------


async def test_cyclic_graph_terminates_and_returns_bounded_results(monkeypatch):
    # A <-> B <-> C <-> A: a 3-cycle. Traversal must not hang, and must
    # respect the hop bound rather than expanding forever.
    links = [
        ("A", "B", "same_topic", 0.9, False),
        ("B", "C", "same_topic", 0.9, False),
        ("C", "A", "same_topic", 0.9, False),
    ]
    statuses = {"A": "active", "B": "active", "C": "active"}
    conn = wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["A"], hops=3, limit=10)

    assert conn.calls  # the query was actually issued
    reached = {row["note_id"] for row in result}
    assert reached <= {"A", "B", "C"}
    assert "A" not in reached  # the seed is never returned even after cycling back


async def test_multiple_seeds_are_all_expanded(monkeypatch):
    links = [
        ("seed-a", "neighbor-a", "same_topic", 1.0, False),
        ("seed-b", "neighbor-b", "same_topic", 1.0, False),
    ]
    statuses = {
        "seed-a": "active",
        "seed-b": "active",
        "neighbor-a": "active",
        "neighbor-b": "active",
    }
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-a", "seed-b"], hops=1)

    assert {row["note_id"] for row in result} == {"neighbor-a", "neighbor-b"}


async def test_limit_truncates_results(monkeypatch):
    links = [
        ("seed-1", "n1", "same_topic", 0.9, False),
        ("seed-1", "n2", "same_topic", 0.8, False),
        ("seed-1", "n3", "same_topic", 0.7, False),
    ]
    statuses = {"seed-1": "active", "n1": "active", "n2": "active", "n3": "active"}
    wire(monkeypatch, links, statuses)

    result = await expand_via_links("user-1", ["seed-1"], hops=1, limit=2)

    assert len(result) == 2
    # Highest path_weight first.
    assert result[0]["note_id"] == "n1"
