"""Graph traversal over ``memory_links`` for multi-hop memory retrieval.

``expand_via_links`` implements an embedding-seeded "PPR-lite": given a
seed set of memory-note ids (typically the top vector-search hits from
``app.memory.retriever``), it walks outward through ``memory_links`` up to
``hops`` steps via a recursive CTE, accumulating a decaying path weight
(``link.weight * 0.5**hop``) so a note reached through several weak/long
hops scores lower than one reached directly. Only active (``invalid_at IS
NULL``) links of relation types that indicate genuine topical/evidential
connection (``same_topic``/``supports``/``elaborates``) are traversed --
``contradicts`` links are deliberately excluded so contradiction edges
don't pull a note's opposite into its own retrieval context.

Cycle safety: the CTE bounds recursion by hop count (``t.hops < :max_hops``
in the recursive term), not by a "visited" set, so a cycle in the link
graph cannot cause unbounded recursion -- it just means a note may be
reached via multiple paths at different hop counts, and the final
``GROUP BY`` collapses those to the best (lowest hops, highest weight)
path per note.
"""

import uuid
from typing import Any

from sqlalchemy import text

from app.memory.db.engine import get_engine

# Relation types considered a genuine "this is related, pull it in" signal for
# retrieval expansion -- not the union of everything in memory_links.relation_type.
_TRAVERSABLE_RELATIONS = ("same_topic", "supports", "elaborates")

# How much a path's weight decays per additional hop.
HOP_DECAY = 0.5

_EXPAND_SQL = text(
    """
    WITH RECURSIVE traversal(note_id, hops, path_weight) AS (
        SELECT n.id, 0, CAST(1.0 AS FLOAT8)
        FROM memory_notes n
        WHERE n.id = ANY(CAST(:seed_ids AS UUID[]))
      UNION ALL
        SELECT
            CASE WHEN l.source_note_id = t.note_id
                 THEN l.target_note_id
                 ELSE l.source_note_id
            END,
            t.hops + 1,
            t.path_weight * l.weight * CAST(:hop_decay AS FLOAT8)
        FROM traversal t
        JOIN memory_links l
          ON l.source_note_id = t.note_id OR l.target_note_id = t.note_id
        WHERE l.invalid_at IS NULL
          AND l.relation_type = ANY(CAST(:relations AS STRING[]))
          AND t.hops < :max_hops
    )
    SELECT tr.note_id AS note_id, min(tr.hops) AS hops, max(tr.path_weight) AS path_weight
    FROM traversal tr
    JOIN memory_notes n ON n.id = tr.note_id
    WHERE tr.hops > 0
      AND tr.note_id != ALL(CAST(:seed_ids AS UUID[]))
      AND n.user_id = :user_id
      AND n.status = 'active'
    GROUP BY tr.note_id
    ORDER BY path_weight DESC
    LIMIT :limit
    """
)


async def expand_via_links(
    user_id: uuid.UUID | str,
    seed_note_ids: list[str],
    *,
    hops: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Expand ``seed_note_ids`` outward via ``memory_links``, up to ``hops`` steps.

    Returns notes newly reached (never the seeds themselves), each as
    ``{"note_id": str, "hops": int, "path_weight": float}``, ordered by
    ``path_weight`` descending. Empty seeds (or ``hops < 1``) short-circuit
    to ``[]`` without touching the database.
    """
    if not seed_note_ids or hops < 1:
        return []

    engine = get_engine()
    async with engine.engine.connect() as conn:
        result = await conn.execute(
            _EXPAND_SQL,
            {
                "seed_ids": [str(x) for x in seed_note_ids],
                "user_id": str(user_id),
                "hop_decay": HOP_DECAY,
                "relations": list(_TRAVERSABLE_RELATIONS),
                "max_hops": hops,
                "limit": limit,
            },
        )
        rows = result.mappings().all()

    return [
        {
            "note_id": str(row["note_id"]),
            "hops": int(row["hops"]),
            "path_weight": float(row["path_weight"]),
        }
        for row in rows
    ]
