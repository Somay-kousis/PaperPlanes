"""Demo-user resolution and upsert (Week 1: single fixed user, no auth yet).

``DEMO_USER_UUID`` is derived deterministically (``uuid5``) from the
API-facing ``DEMO_USER_ID = "demo"`` string, so the same UUID is produced
on every process start without needing to look anything up first --
useful since ``users.id`` is what ``sessions``/``papers``/``episodes``
foreign-key against.
"""

import uuid

from sqlalchemy import text

from app.api.schema.chat import DEMO_USER_ID
from app.memory.db.engine import get_engine

# Fixed namespace UUID for this app; combined with a name via uuid5 so the
# demo user's id is stable across restarts/environments without a lookup.
_NAMESPACE = uuid.UUID("f3b1a4b0-3e6b-4b7b-9b1a-2f6b3c4d5e6f")

DEMO_USER_UUID = uuid.uuid5(_NAMESPACE, DEMO_USER_ID)
DEMO_USER_EMAIL = "demo@paperplanes.local"


def resolve_user_id(user_id: str) -> uuid.UUID:
    """Map an API-facing ``user_id`` string to its database UUID.

    Only the demo user is supported in Week 1; any other value is assumed
    to already be a UUID string (future multi-user support).
    """
    if user_id == DEMO_USER_ID:
        return DEMO_USER_UUID
    return uuid.UUID(user_id)


async def ensure_user(user_uuid: uuid.UUID, email: str | None = None) -> uuid.UUID:
    """Upsert a user row for ``user_uuid``; idempotent, safe to call every request.

    Any session/paper/note the caller then writes foreign-keys against this row,
    so this must run before those writes for ANY user -- not just the demo user.
    A synthetic ``<uuid>@paperplanes.local`` email is used when none is given
    (the column is only ``UNIQUE NOT NULL``, not a real contact address here).
    """
    email = email or f"{user_uuid}@paperplanes.local"
    engine = get_engine()
    async with engine.engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (id, email) VALUES (:id, :email) ON CONFLICT (id) DO NOTHING"),
            {"id": str(user_uuid), "email": email},
        )
    return user_uuid


async def ensure_demo_user() -> uuid.UUID:
    """Upsert the demo user's row; idempotent, safe to call every request."""
    return await ensure_user(DEMO_USER_UUID, DEMO_USER_EMAIL)
