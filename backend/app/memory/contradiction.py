"""Contradiction detection and resolution for claims (Week 3 knowledge graph).

Responsibilities:
- ``judge``: run the ``contradiction_judge.md`` prompt over a pair of
  claims and decide whether they genuinely conflict, support each other,
  or are unrelated. Degrades to an ``"unrelated"`` verdict (never raises)
  on any model failure, so a single bad judge call can't abort ingestion.
- ``check_claim``: find candidate contradictions for one new claim
  (semantically similar, cross-paper, same-subject-preferred existing
  active claims) and judge each one, returning every judged candidate so
  the caller (``app.core.nodes.ingestion.contradiction_check_node``)
  decides what to do with a ``"contradicts"`` verdict -- this module only
  detects and judges, it never mutates ``claims``/``contradictions``
  itself.
- ``resolve``: mark a ``contradictions`` row resolved with an
  explanatory note (thin wrapper over
  ``app.memory.db.contradictions_repo.resolve_contradiction``, the single
  entry point the API route calls).
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.memory.scoring import l2_distance_to_cosine_similarity

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "core" / "prompts" / "contradiction_judge.md"

# Candidates below this cosine similarity aren't even worth an LLM judge call --
# they're too dissimilar to plausibly be about the same fact.
CONTRADICTION_SIMILARITY_FLOOR = 0.6
DEFAULT_CANDIDATE_LIMIT = 5


@lru_cache
def _load_judge_prompt() -> str:
    return _PROMPT_PATH.read_text()


class ContradictionVerdict(BaseModel):
    """Structured output for the contradiction-judge prompt."""

    relation: Literal["contradicts", "supports", "unrelated"]
    rationale: str = Field(description="One or two sentence justification for the verdict.")


def _claim_summary(claim: dict[str, Any]) -> str:
    return json.dumps(
        {"statement": claim.get("statement"), "predicate": claim.get("predicate")}
    )


async def judge(
    claim_a: dict[str, Any], claim_b: dict[str, Any], *, model: Any = None
) -> ContradictionVerdict:
    """Run the contradiction-judge prompt over two claims.

    Degrades to an ``"unrelated"`` verdict (never raises) on any model
    failure -- callers that need per-candidate isolation may still wrap
    this, but this function itself never lets a Bedrock error escape.
    """
    try:
        if model is None:
            from app.core.models.llm import get_fast_model

            model = get_fast_model()
        structured = model.with_structured_output(ContradictionVerdict)
        prompt = _load_judge_prompt().format(
            claim_a=_claim_summary(claim_a), claim_b=_claim_summary(claim_b)
        )
        verdict = structured.invoke(prompt)
        if not isinstance(verdict, ContradictionVerdict):
            verdict = ContradictionVerdict.model_validate(verdict)
        return verdict
    except Exception:
        logger.warning("Contradiction judge failed; defaulting to 'unrelated'", exc_info=True)
        return ContradictionVerdict(
            relation="unrelated", rationale="judge unavailable; defaulted to unrelated"
        )


async def check_claim(
    user_id: str, claim: dict[str, Any], *, limit: int = DEFAULT_CANDIDATE_LIMIT
) -> list[dict[str, Any]]:
    """Find & judge cross-paper contradiction candidates for ``claim``.

    ``claim`` must carry an ``"embedding"`` (already normalized) and a
    ``"paper_id"``. Searches active claims for ``user_id`` similar to
    ``claim``, preferring ones sharing its ``subject_entity_id``,
    excludes candidates from the same paper (this is cross-paper
    detection only) and the claim itself, then judges every candidate
    whose similarity clears ``CONTRADICTION_SIMILARITY_FLOOR``.

    Returns a list of ``{"candidate": <claim dict>, "relation":,
    "rationale":, "similarity":}`` for every candidate judged (regardless
    of verdict) -- the caller decides what to do with each. A judge
    failure for one candidate is logged and that candidate is simply
    omitted from the results, isolated from the rest.
    """
    from app.memory.db import claims_repo

    embedding = claim.get("embedding")
    if not embedding:
        return []

    candidates = await claims_repo.search_similar_active_claims(
        user_id,
        embedding,
        subject_entity_id=claim.get("subject_entity_id"),
        limit=limit,
    )

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("id") == claim.get("id"):
            continue
        if candidate.get("paper_id") == claim.get("paper_id"):
            continue

        similarity = l2_distance_to_cosine_similarity(candidate["distance"])
        if similarity < CONTRADICTION_SIMILARITY_FLOOR:
            continue

        try:
            verdict = await judge(claim, candidate)
        except Exception:
            logger.warning(
                "Contradiction judge raised for claim %s vs candidate %s; skipping",
                claim.get("id"),
                candidate.get("id"),
                exc_info=True,
            )
            continue

        results.append(
            {
                "candidate": candidate,
                "relation": verdict.relation,
                "rationale": verdict.rationale,
                "similarity": similarity,
            }
        )
    return results


async def resolve(
    contradiction_id: str, *, resolution_note: str | None = None
) -> dict[str, Any] | None:
    """Mark a contradiction resolved with an explanatory note."""
    from app.memory.db import contradictions_repo

    return await contradictions_repo.resolve_contradiction(contradiction_id, resolution_note)
