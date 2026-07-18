"""contradiction_check_node: flags cross-paper claims that conflict.

For each newly extracted claim in ``state["claims"]``, calls
``app.memory.contradiction.check_claim`` to find semantically similar,
cross-paper, active claims and judge whether they truly conflict. On a
``"contradicts"`` verdict, BOTH claims are flagged ``disputed`` (never
hard-invalidated -- a cross-paper disagreement means both stand, just
flagged) via ``claims_repo.mark_disputed``, a ``contradictions`` row is
inserted, and an audit ``"add"`` entry is written against it. Invalidation
(``claims_repo.invalidate_claim``) is reserved for a different scenario --
the same source superseding its own earlier claim -- not exercised here.

Self-degrades like every other ingestion step: a failure checking one
claim, or recording one contradiction, is logged and isolated so it never
aborts the rest of the paper's contradiction pass or the ingestion run.
"""

import logging
from typing import Any

from app.core.graph.state import IngestionState

logger = logging.getLogger(__name__)

_ACTOR = "system:contradiction_check"


async def contradiction_check_node(
    state: IngestionState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Detect contradictions between new and existing claims."""
    if state.get("status") == "failed":
        return {}

    claims = state.get("claims", [])
    if not claims:
        return {"contradictions": []}

    user_id = state["user_id"]

    from app.memory import audit
    from app.memory.contradiction import check_claim
    from app.memory.db import claims_repo, contradictions_repo

    found: list[dict[str, Any]] = []
    disputed: set[str] = set()

    for claim in claims:
        try:
            results = await check_claim(user_id, claim)
        except Exception:
            logger.warning(
                "Contradiction check failed for claim %s; skipping", claim.get("id"), exc_info=True
            )
            continue

        for result in results:
            if result["relation"] != "contradicts":
                continue

            candidate = result["candidate"]
            try:
                if claim["id"] not in disputed:
                    await claims_repo.mark_disputed(claim["id"])
                    disputed.add(claim["id"])
                if candidate["id"] not in disputed:
                    await claims_repo.mark_disputed(candidate["id"])
                    disputed.add(candidate["id"])

                row = await contradictions_repo.insert_contradiction(
                    claim["id"], candidate["id"], result["rationale"]
                )
                await audit.write_audit(
                    None,
                    user_id=user_id,
                    actor=_ACTOR,
                    action="add",
                    target_table="contradictions",
                    target_id=row["id"],
                    reason=result["rationale"],
                    details={"claim_a": claim["id"], "claim_b": candidate["id"]},
                )
                found.append(row)
            except Exception:
                logger.warning(
                    "Failed to record contradiction between claims %s and %s",
                    claim.get("id"),
                    candidate.get("id"),
                    exc_info=True,
                )
                continue

    return {"contradictions": found}
