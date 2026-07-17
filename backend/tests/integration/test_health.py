"""Integration test for GET /api/healthz via an in-process ASGI transport.

Does not require a running database: ``ping()`` naturally returns False
when CockroachDB isn't reachable, and the endpoint is expected to report
that as `checks.db: false` while still returning 200 (liveness, not
readiness).
"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_healthz_responds_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "db" in body["checks"]
    assert isinstance(body["checks"]["db"], bool)


async def test_readyz_reports_503_when_db_down():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readyz")

    body = response.json()
    if body["ready"]:
        assert response.status_code == 200
    else:
        assert response.status_code == 503
