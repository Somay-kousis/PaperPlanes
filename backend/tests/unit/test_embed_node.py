"""Tests for app.core.nodes.ingestion.embed_node: mocked-boto3 embedding calls.

No real AWS calls: ``embed_texts`` accepts an injectable ``client``, so
these tests pass a fake object mimicking the bits of the boto3
``bedrock-runtime`` client's ``invoke_model`` response we rely on.
"""

import io
import json

import pytest

from app.core.nodes.ingestion.embed_node import embed_node, embed_texts


class _FakeBody:
    def __init__(self, payload: dict):
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self):
        return self._buf.read()


class _HappyClient:
    """Always succeeds, returning a deterministic embedding per call."""

    def __init__(self):
        self.calls = []

    def invoke_model(self, *, modelId, body, contentType, accept):
        self.calls.append(json.loads(body))
        return {"body": _FakeBody({"embedding": [0.1, 0.2, 0.3]})}


class _FlakyClient:
    """Fails the first N calls per-text, then succeeds."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.attempts = 0

    def invoke_model(self, *, modelId, body, contentType, accept):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError("throttled")
        return {"body": _FakeBody({"embedding": [1.0, 0.0]})}


class _AlwaysFailsClient:
    def invoke_model(self, *, modelId, body, contentType, accept):
        raise RuntimeError("permanently down")


async def test_embed_texts_happy_path_returns_one_vector_per_text():
    client = _HappyClient()
    vectors = await embed_texts(["a", "b", "c"], client=client)
    assert vectors == [[0.1, 0.2, 0.3]] * 3
    assert len(client.calls) == 3


async def test_embed_texts_sends_expected_request_body():
    client = _HappyClient()
    await embed_texts(["hello world"], client=client)
    body = client.calls[0]
    assert body["inputText"] == "hello world"
    assert body["normalize"] is True
    assert "dimensions" in body


async def test_embed_texts_retries_transient_failures_then_succeeds():
    client = _FlakyClient(fail_times=2)
    vectors = await embed_texts(["only one"], client=client, concurrency=1)
    assert vectors == [[1.0, 0.0]]
    assert client.attempts == 3  # 2 failures + 1 success


async def test_embed_texts_raises_after_exhausting_retries():
    client = _AlwaysFailsClient()
    with pytest.raises(RuntimeError):
        await embed_texts(["doomed"], client=client, concurrency=1)


async def test_embed_texts_respects_small_concurrency_with_many_texts():
    client = _HappyClient()
    texts = [f"chunk {i}" for i in range(10)]
    vectors = await embed_texts(texts, client=client, concurrency=2)
    assert len(vectors) == 10
    assert len(client.calls) == 10


async def test_embed_node_short_circuits_on_prior_failure():
    result = await embed_node({"status": "failed", "fail_reason": "already broken"})
    assert result == {}


async def test_embed_node_fails_when_no_chunks(monkeypatch):
    async def fake_update_status(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.memory.db.papers_repo.update_paper_status", fake_update_status
    )
    result = await embed_node({"paper_id": "p1", "chunks": []})
    assert result["status"] == "failed"


async def test_embed_node_attaches_normalized_embeddings(monkeypatch):
    async def fake_update_status(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.memory.db.papers_repo.update_paper_status", fake_update_status
    )

    async def fake_embed_texts(texts, **kwargs):
        return [[3.0, 4.0] for _ in texts]

    monkeypatch.setattr(
        "app.core.nodes.ingestion.embed_node.embed_texts", fake_embed_texts
    )

    state = {
        "paper_id": "p1",
        "chunks": [
            {"chunk_index": 0, "page_number": 1, "text": "hello", "token_count": 2},
            {"chunk_index": 1, "page_number": 1, "text": "world", "token_count": 2},
        ],
    }
    result = await embed_node(state)
    assert len(result["chunks"]) == 2
    for chunk in result["chunks"]:
        # normalize_embedding([3.0, 4.0]) has unit L2 norm.
        norm = sum(c * c for c in chunk["embedding"]) ** 0.5
        assert norm == pytest.approx(1.0)
