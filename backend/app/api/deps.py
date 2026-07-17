"""Shared FastAPI dependencies -- currently just API-token authentication.

``require_api_token`` gates the data routes (chat, papers, memory, contradictions,
reflections). It is *opt-in*: when ``Settings.APP_API_TOKEN`` is unset the check is
a no-op, so local dev, CI, and the eval suite keep working without a token; when
it is set (as any real deployment must), every request to a gated route needs a
matching ``Authorization: Bearer <token>`` header. Health/readiness routes are
deliberately left ungated so probes and load balancers don't need the token.

This closes the "unauthenticated, anyone can reach the memory layer" hole. It does
NOT by itself fix the client-supplied ``user_id`` (IDOR) design -- in a real
multi-tenant deployment ``user_id`` should be derived from the authenticated
identity rather than the request body -- but with a single shared token the token
holder *is* the (single) user, so cross-user access is no longer reachable by an
anonymous caller.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Enforce a bearer token on gated routes when ``APP_API_TOKEN`` is configured.

    No-op when the token isn't set. When it is, a missing/malformed/incorrect
    token yields 401. The comparison is constant-time to avoid leaking the token
    via response timing.
    """
    expected = get_settings().APP_API_TOKEN
    if not expected:
        return
    provided = _extract_bearer(authorization)
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
