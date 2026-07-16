"""Pure scoring functions for the memory engine.

These implement the memory-strength math used to rank and decay memory
notes. All functions here are pure (no I/O, no randomness) so they are
fully unit-testable and safe to call from any node without a DB or model
dependency.
"""

import math


def ebbinghaus_retention(dt_seconds: float, strength: float) -> float:
    """Return the probability of recall R given elapsed time and strength.

    Implements the Ebbinghaus forgetting curve:

        R = e^(-Δt / S)

    where ``Δt`` (``dt_seconds``) is the elapsed time since the memory was
    last accessed/reinforced, and ``S`` (``strength``) is the memory's
    current "stability" -- larger S means slower decay. Both are expected
    in the same time unit (this module treats them as seconds, but the
    formula is unit-agnostic as long as both arguments share units).

    Returns a value in (0, 1]. ``dt_seconds=0`` returns 1.0 (perfect
    recall). ``strength`` must be > 0; a non-positive strength is treated
    as an immediate, complete decay (returns 0.0) rather than raising, so
    callers can score notes without special-casing corrupt data.
    """
    if strength <= 0:
        return 0.0
    if dt_seconds <= 0:
        return 1.0
    return math.exp(-dt_seconds / strength)


def reinforce(strength: float, access_count: int) -> float:
    """Return the new strength after a memory is accessed/reinforced again.

    Each reinforcement increases stability with diminishing returns:

        S' = S * (1 + 1 / (access_count + 1))

    So the first reinforcement (access_count=0) roughly doubles strength,
    the second (access_count=1) adds 50%, and so on -- modeling spaced
    repetition, where each additional review yields a smaller relative
    boost to how long the memory persists before it needs reviewing again.

    ``access_count`` is the number of PRIOR accesses (i.e. before this
    reinforcement), so it must be >= 0.
    """
    if access_count < 0:
        raise ValueError("access_count must be >= 0")
    if strength <= 0:
        raise ValueError("strength must be > 0")
    return strength * (1 + 1 / (access_count + 1))


def combined_score(
    recency: float,
    importance: float,
    relevance: float,
    *,
    recency_weight: float = 0.3,
    importance_weight: float = 0.3,
    relevance_weight: float = 0.4,
) -> float:
    """Return a single ranking score combining recency, importance, relevance.

    ``recency`` is expected to be the Ebbinghaus retention R in [0, 1]
    (i.e. the output of ``ebbinghaus_retention``), ``importance`` the
    note's stored importance in [0, 1], and ``relevance`` the
    query-similarity score in [0, 1] (e.g. cosine similarity of
    normalized embeddings, which is already bounded to [-1, 1] but for
    normalized non-negative embedding spaces is effectively [0, 1]).

    The result is a weighted sum, so with default weights (which sum to
    1.0) and all three inputs in [0, 1], the output is also in [0, 1].
    Weights need not sum to 1; callers passing custom weights are
    responsible for the resulting scale.
    """
    return (
        recency_weight * recency
        + importance_weight * importance
        + relevance_weight * relevance
    )


def l2_distance_to_cosine_similarity(distance: float) -> float:
    """Convert an L2 distance between two unit vectors into cosine similarity.

    For unit-norm vectors ``a``/``b`` (i.e. anything that has passed
    through ``app.memory.db.vectorstore.normalize_embedding``),
    ``||a - b||^2 = 2 - 2*cos(a, b)``, so ``cos(a, b) = 1 - distance^2 / 2``.
    This is the single choke point for that conversion so the memory
    writer (dedup/link thresholds) and retriever (relevance scoring) agree
    on what "similarity" means for a given ANN distance. The result is
    clamped to ``[-1.0, 1.0]`` to absorb floating-point noise for
    near-identical or near-antipodal vectors.
    """
    similarity = 1.0 - (distance * distance) / 2.0
    return max(-1.0, min(1.0, similarity))
