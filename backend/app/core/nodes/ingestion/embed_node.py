"""embed_node: computes embeddings for each chunk via Bedrock Titan v2.

Calls ``bedrock-runtime.invoke_model`` once per chunk (boto3 is
synchronous, so each call runs in a worker thread via
``asyncio.to_thread``), bounded to ``concurrency`` in flight at a time via
an ``asyncio.Semaphore``, with a small retry loop per chunk. Every raw
vector is passed through
``app.memory.db.vectorstore.normalize_embedding`` before being attached
back onto its chunk -- this is the single normalization choke point for
anything written to a ``VECTOR`` column.
"""

import asyncio
import json
import logging
import time
from typing import Any

from app.core.graph.state import IngestionState
from app.memory.db.vectorstore import normalize_embedding

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
CONCURRENCY = 4
_RETRY_BASE_DELAY = 0.2


def _invoke_embed_sync(client: Any, model_id: str, text: str, dimensions: int) -> list[float]:
    """Call ``invoke_model`` for a single chunk, retrying transient failures."""
    body = json.dumps({"inputText": text, "dimensions": dimensions, "normalize": True})
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read())
            return payload["embedding"]
        except Exception as exc:  # noqa: BLE001 - retried below, re-raised on exhaustion
            last_exc = exc
            if attempt == MAX_ATTEMPTS - 1:
                raise
            logger.warning(
                "Embedding call failed (attempt %d/%d), retrying: %s",
                attempt + 1,
                MAX_ATTEMPTS,
                exc,
            )
            time.sleep(_RETRY_BASE_DELAY * (attempt + 1))
    raise last_exc  # pragma: no cover - unreachable: loop above always returns or raises


async def embed_texts(
    texts: list[str], *, client: Any = None, concurrency: int = CONCURRENCY
) -> list[list[float]]:
    """Embed each of ``texts`` via Bedrock Titan v2, ``concurrency`` at a time.

    ``client`` is injectable so tests can pass a mock boto3 client instead
    of constructing a real one (which requires AWS credentials).
    """
    from app.core.config import get_settings

    settings = get_settings()
    if client is None:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)

    semaphore = asyncio.Semaphore(concurrency)

    async def _embed_one(text: str) -> list[float]:
        async with semaphore:
            return await asyncio.to_thread(
                _invoke_embed_sync,
                client,
                settings.BEDROCK_EMBED_MODEL_ID,
                text,
                settings.EMBED_DIM,
            )

    return list(await asyncio.gather(*(_embed_one(t) for t in texts)))


async def embed_node(state: IngestionState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute and attach normalized embeddings for each chunk.

    Also flips ``papers.status`` to ``"embedding"`` before the batch
    starts, so ``GET /api/papers/{id}/status`` reflects progress while
    this (potentially slow) step is running.
    """
    if state.get("status") == "failed":
        return {}

    chunks = state.get("chunks", [])
    if not chunks:
        return {"status": "failed", "fail_reason": "No chunks to embed"}

    from app.memory.db import papers_repo

    await papers_repo.update_paper_status(state["paper_id"], "embedding")

    try:
        vectors = await embed_texts([chunk["text"] for chunk in chunks])
    except Exception as exc:
        logger.exception("Embedding failed for paper %s", state.get("paper_id"))
        return {"status": "failed", "fail_reason": f"Embedding failed: {exc}"}

    embedded = [
        {**chunk, "embedding": normalize_embedding(vector)}
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    return {"chunks": embedded}
