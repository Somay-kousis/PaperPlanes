"""Audit logging for memory mutations.

Every write/invalidate/update/read against ``memory_notes``/``memory_links``
appends a row to ``memory_audit_log`` recording the actor (e.g.
``"system:memory_writer"``, ``"system:retriever"``), action, target
table/id, reason, and a ``details`` JSONB blob (typically a before/after
snapshot for update/invalidate) -- giving a full, queryable history of why
memory changed over time.

``write_audit`` takes an optional connection/session as its first
argument so callers already inside a transaction (e.g. a note mutation)
can have the audit row committed atomically with it; callers with no
transaction of their own (e.g. a plain read-triggered reinforcement) pass
``None`` and this opens its own short transaction.
"""

import json
import uuid
from typing import Any, Protocol

from sqlalchemy import text

from app.memory.db.engine import get_engine

_INSERT_AUDIT_SQL = text(
    """
    INSERT INTO memory_audit_log
        (id, user_id, actor, action, target_table, target_id, reason, details)
    VALUES
        (:id, :user_id, :actor, :action, :target_table, :target_id, :reason,
         CAST(:details AS JSONB))
    """
)


class _ExecutableConn(Protocol):
    async def execute(self, statement: Any, parameters: dict[str, Any] | None = None) -> Any: ...


async def write_audit(
    conn_or_session: _ExecutableConn | None = None,
    *,
    user_id: uuid.UUID | str,
    actor: str,
    action: str,
    target_table: str,
    target_id: uuid.UUID | str,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Append a row to ``memory_audit_log``, returning the new row's id.

    ``action`` is expected to be one of ``add``/``update``/``invalidate``/
    ``read`` (see ``app.memory.writer``/``app.memory.retriever``), but this
    function does not validate it -- callers own that vocabulary.
    """
    audit_id = uuid.uuid4()
    params = {
        "id": str(audit_id),
        "user_id": str(user_id),
        "actor": actor,
        "action": action,
        "target_table": target_table,
        "target_id": str(target_id),
        "reason": reason,
        "details": json.dumps(details or {}, default=str),
    }

    if conn_or_session is not None:
        await conn_or_session.execute(_INSERT_AUDIT_SQL, params)
    else:
        engine = get_engine()
        async with engine.engine.begin() as conn:
            await conn.execute(_INSERT_AUDIT_SQL, params)

    return str(audit_id)
