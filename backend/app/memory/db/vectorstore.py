"""Vector storage helpers.

``normalize_embedding`` is THE single choke point for embedding
normalization in this codebase: every embedding written to or compared
against ``chunks``, ``memory_notes``, ``entities``, or ``claims`` MUST
pass through this function first. Centralizing it here means a future
change to the normalization scheme (or the embedding model / dimension)
only has to happen in one place, and it means cosine similarity and inner
product are equivalent for anything stored this way (since all vectors
have unit L2 norm).
"""

import math
from typing import Any

from app.core.config import get_settings


def normalize_embedding(vec: list[float]) -> list[float]:
    """Return ``vec`` scaled to unit L2 norm.

    A zero vector (or a vector whose norm underflows to 0.0) cannot be
    normalized without dividing by zero; rather than raising, this returns
    the input unchanged (still all zeros) so callers can persist a "null"
    embedding without special-casing it downstream. This is a deliberate
    choice: a zero vector after normalization is still a zero vector, and
    it will simply score as unrelated to everything (cosine similarity
    against it is 0), which is the desired degraded behavior.
    """
    norm = math.sqrt(sum(component * component for component in vec))
    if norm == 0.0:
        return list(vec)
    return [component / norm for component in vec]


def get_vector_store(table: str, namespace: str | None = None) -> Any:
    """Return a vector-store handle scoped to ``table`` (and optional namespace).

    Week 1+ responsibility: wrap CockroachDB VECTOR columns (chunks,
    memory_notes, entities, claims) behind a common similarity-search
    interface, likely built on ``langchain_cockroachdb`` primitives plus
    ``app.memory.db.engine`` for the underlying connection. ``table`` must
    be one of the tables with a VECTOR(EMBED_DIM) column (see
    ``app/memory/db/migrations``); ``namespace`` will typically be a
    ``user_id`` for per-user row-level scoping.
    """
    get_settings()  # touch settings so EMBED_DIM/table wiring is validated early once implemented
    raise NotImplementedError
