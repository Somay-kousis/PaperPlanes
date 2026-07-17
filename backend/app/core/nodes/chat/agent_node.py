"""agent_node: the chat graph's response-generating node.

``agent_echo_node`` is the deterministic Week 0 fallback: a no-network
echo responder, safe to exercise in unit tests without any AWS
credentials. ``agent_node`` is the unified Week 1+ entry point the graph
actually uses: it renders ``state["retrieved_chunks"]`` (populated by
``retrieve_node``) into numbered context blocks, calls
ChatBedrockConverse, and falls back to the echo responder -- setting
``used_model``/``citations`` accordingly -- whenever AWS credentials
aren't configured or the Bedrock call itself raises. This means
``agent_node`` itself never needs gating by callers; it degrades on its
own, which is what keeps it safe to route through in every environment
(including CI, where ``Settings.has_aws_credentials`` is always False).
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from app.core.graph.state import ChatState
from app.core.nodes.chat.utils import last_human_text

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "system_chat.md"

# How many model<->tool round-trips the introspection loop will run before it
# stops asking for more SQL and forces a final natural-language answer.
_MAX_TOOL_ITERS = 3

_INTROSPECT_ADDENDUM_TEMPLATE = (
    "\n\nYou also have a `memory_introspect` tool: it runs a single read-only "
    "SQL SELECT against your own CockroachDB memory store (through CockroachDB "
    "Cloud's audited Managed MCP Server) so you can answer meta-questions about "
    "your own memory -- how many papers you've read, how many memory notes or "
    "contradictions you hold, your busiest topics, recent activity. Use it ONLY "
    "for such meta-questions, not for ordinary research answers (those come from "
    "the retrieved excerpts and memory notes above). Qualify table names with the "
    "database and schema, e.g. `{db}.public.memory_notes`, `{db}.public.papers`, "
    "`{db}.public.claims`, `{db}.public.contradictions`, `{db}.public.reflections`."
)


def _introspect_addendum(db: str) -> str:
    return _INTROSPECT_ADDENDUM_TEMPLATE.format(db=db)


class MemoryIntrospect(BaseModel):
    """Run a read-only SQL SELECT against your own CockroachDB memory store.

    Use this to answer meta-questions about your memory (counts of papers,
    notes, claims, or contradictions; table sizes; recent activity). The
    statement MUST be a single read-only SELECT and MUST qualify table names
    with their database and schema (e.g. paperplanes_prod.public.memory_notes).
    """

    query: str = Field(description="A single read-only SQL SELECT statement.")


@lru_cache
def _load_system_prompt_template() -> str:
    return _SYSTEM_PROMPT_PATH.read_text()


def _format_context_blocks(chunks: list[dict[str, Any]]) -> str:
    """Render retrieved chunks as numbered ``[1]..[n]`` context blocks."""
    if not chunks:
        return "(No paper excerpts were retrieved for this turn.)"
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        title = chunk.get("paper_title") or "Untitled paper"
        page = chunk.get("page_number")
        location = f"{title}, p. {page}" if page is not None else title
        blocks.append(f"[{i}] {location}\n{chunk.get('text', '')}")
    return "\n\n".join(blocks)


def _citations_from_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the citation payload (chunk_id/paper_id/title/page/snippet)."""
    citations = []
    for chunk in chunks:
        text = chunk.get("text", "")
        citations.append(
            {
                "chunk_id": chunk["chunk_id"],
                "paper_id": chunk["paper_id"],
                "paper_title": chunk.get("paper_title"),
                "page_number": chunk.get("page_number"),
                "snippet": text[:200],
            }
        )
    return citations


def agent_echo_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deterministic echo agent: WORKING, used whenever AWS isn't configured.

    Returns an AIMessage of the form ``"PaperPlanes received: <text>"`` for
    the most recent human message in state. No network calls, no AWS
    dependency -- safe to run in tests and without credentials configured.
    """
    messages = state.get("messages", [])
    last_text = last_human_text(messages)
    reply = f"PaperPlanes received: {last_text}"
    return {"messages": [AIMessage(content=reply)]}


async def _run_with_introspection(
    model: Any, messages: list[Any], user_id: str | None, session_id: str | None
) -> Any:
    """Invoke the model with the ``memory_introspect`` MCP tool bound, in a loop.

    Runs a bounded model<->tool exchange: the model may emit
    ``MemoryIntrospect`` tool calls, each of which is executed as a read-only
    query against the agent's own CockroachDB memory store via the Managed MCP
    Server (``mcp_client.run_read_query``), with the result fed back as a
    ``ToolMessage``. Stops as soon as the model answers without a tool call, or
    after ``_MAX_TOOL_ITERS`` round-trips (a final answer is then forced). Any
    single query failure is surfaced to the model as an error string rather than
    raising, so it can recover or answer without the data.
    """
    from app.memory import mcp_client

    bound = model.bind_tools([MemoryIntrospect])
    convo = list(messages)

    for _ in range(_MAX_TOOL_ITERS):
        ai = await bound.ainvoke(convo)
        convo.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            return ai
        for call in tool_calls:
            query = (call.get("args") or {}).get("query", "")
            ok = True
            try:
                result = await mcp_client.run_read_query(query)
            except Exception:  # includes MCPError -- report cleanly, never raise
                # Deliberately do NOT surface the raw SQL/DB error to the model:
                # it tends to parrot it verbatim into the user-facing answer.
                # Give it a neutral instruction to fall back instead.
                logger.warning("memory_introspect query failed", exc_info=True)
                ok = False
                result = (
                    "The memory store could not be queried for this request. Answer the "
                    "user's question using your other context, and do not mention this tool, "
                    "SQL, or any database error."
                )
            await _audit_introspection(user_id, session_id, query, ok=ok)
            convo.append(ToolMessage(content=str(result)[:4000], tool_call_id=call["id"]))

    # Out of tool iterations: force a final natural-language answer.
    return await bound.ainvoke(convo)


async def _audit_introspection(
    user_id: str | None, session_id: str | None, query: str, *, ok: bool
) -> None:
    """Record an agent ``memory_introspect`` SQL query in the memory audit log.

    The MCP tool is the agent's most powerful action (read-only SQL over its own
    store), so it belongs in the same audit trail as reads/writes -- not only in
    CockroachDB Cloud's server-side log. Best-effort: a missing user/session id
    or an audit-write failure is swallowed so it never affects the chat turn.
    ``target_id`` is the session id (the context the query ran in).
    """
    if not user_id or not session_id:
        return
    try:
        from app.memory import audit

        await audit.write_audit(
            None,
            user_id=user_id,
            actor="agent:memory_introspect",
            action="read",
            target_table="mcp:memory_store",
            target_id=session_id,
            reason=query[:500],
            details={"tool": "memory_introspect", "ok": ok, "query": query[:2000]},
        )
    except Exception:
        logger.warning("Failed to audit memory_introspect query", exc_info=True)


async def agent_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Unified chat agent: real Bedrock model with RAG context, or echo.

    This is the node wired into ``build_chat_graph``. It self-gates on
    ``Settings.has_aws_credentials`` and on any invocation error, so the
    graph never needs a separate echo-vs-real branch at the route level. When
    the Managed MCP Server is configured, the model is given a
    ``memory_introspect`` tool for read-only meta-questions about its own
    memory store (see ``_run_with_introspection``); otherwise it answers in a
    single shot.
    """
    from app.core.config import get_settings

    settings = get_settings()
    retrieved_chunks = state.get("retrieved_chunks", [])

    if not settings.has_aws_credentials:
        return {**agent_echo_node(state, config), "used_model": "echo", "citations": []}

    try:
        from app.core.models.llm import get_chat_model
        from app.memory import mcp_client

        memory_block = state.get("memory_context_block") or (
            "(No memory notes retrieved for this turn.)"
        )
        system_prompt = _load_system_prompt_template().format(
            context_blocks=_format_context_blocks(retrieved_chunks),
            memory_block=memory_block,
        )
        introspect = mcp_client.is_configured()
        if introspect:
            system_prompt += _introspect_addendum(settings.MCP_MEMORY_DATABASE)
        model = get_chat_model()
        messages = [SystemMessage(content=system_prompt), *state.get("messages", [])]
        if introspect:
            response = await _run_with_introspection(
                model, messages, state.get("user_id"), state.get("session_id")
            )
        else:
            response = await model.ainvoke(messages)
        citations = _citations_from_chunks(retrieved_chunks)
        return {
            "messages": [response],
            "used_model": settings.BEDROCK_CHAT_MODEL_ID,
            "citations": citations,
        }
    except Exception:
        logger.warning("Bedrock agent invocation failed; falling back to echo", exc_info=True)
        return {**agent_echo_node(state, config), "used_model": "echo", "citations": []}


def agent_bedrock_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Real Bedrock-backed chat agent, with no echo fallback.

    Lazily imports ``app.core.models.llm.get_chat_model`` so importing this
    module never requires AWS credentials or the boto3/langchain-aws stack
    to be configured. Kept as a standalone building block (e.g. for a
    future streaming node); ``agent_node`` above -- which wraps this same
    call with fallback/citation logic -- is what the compiled graph uses.
    """
    from app.core.models.llm import get_chat_model

    model = get_chat_model()
    messages = state.get("messages", [])
    response = model.invoke(messages)
    return {"messages": [response]}
