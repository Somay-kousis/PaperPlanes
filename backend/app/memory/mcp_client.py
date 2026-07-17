"""Client for the CockroachDB Cloud **Managed MCP Server**.

This is one of the two required CockroachDB hackathon tools. The managed MCP
server (``https://cockroachlabs.cloud/mcp``) is a standard MCP *Streamable
HTTP* endpoint, OAuth-protected, that accepts a service-account API key as a
bearer token (``Authorization: Bearer <key>``; scopes ``mcp:read`` /
``mcp:write``). It exposes read tools over the user's own cluster --
``list_databases``, ``get_table_schema``, ``select_query``, ``EXPLAIN`` -- with
server-side audit logging.

PaperPlanes uses it for *agentic self-introspection*: the chat agent answers
meta-questions about its own memory ("how many papers have I read?", "how big
are my memory tables?", "how many contradictions were found this week?") by
letting the model compose a read-only SQL query which is executed against the
agent's own schema through this server, rather than through the app's normal
SQLAlchemy path. That the agent inspects its memory store through the same
managed, audited control plane a human operator would use is the point.

Implemented with raw ``httpx`` (no MCP SDK dependency): initialize -> notify
initialized -> tools/list -> tools/call, handling both ``application/json`` and
``text/event-stream`` (SSE) response framing. Everything degrades gracefully:
with no ``MCP_ENDPOINT``/``MCP_API_KEY`` configured, ``is_configured`` is False
and callers skip the MCP path.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2025-06-18"
_CLIENT_INFO = {"name": "paperplanes", "version": "0.1"}
_ACCEPT = "application/json, text/event-stream"


class MCPError(RuntimeError):
    """Raised when the MCP server returns a JSON-RPC error or a bad response."""


def _parse_jsonrpc(resp: httpx.Response) -> dict[str, Any]:
    """Extract a single JSON-RPC result object from a Streamable-HTTP response.

    The server may reply with ``application/json`` (one object) or
    ``text/event-stream`` (SSE frames); for a single request we take the last
    ``data:`` frame carrying a JSON-RPC envelope.
    """
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        payload: dict[str, Any] | None = None
        for raw in resp.text.splitlines():
            line = raw.strip()
            if line.startswith("data:"):
                chunk = line[len("data:") :].strip()
                if not chunk:
                    continue
                try:
                    obj = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                    payload = obj
        if payload is None:
            raise MCPError("No JSON-RPC data frame in SSE response")
        return payload
    return resp.json()


class MCPClient:
    """Async client for a single MCP Streamable-HTTP session.

    Use as an async context manager::

        async with MCPClient(endpoint, api_key) as mcp:
            tools = await mcp.list_tools()
            result = await mcp.call_tool("select_query", {"statement": "..."})
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        *,
        cluster_id: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.cluster_id = cluster_id
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._id = 0

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": _ACCEPT,
            "MCP-Protocol-Version": _PROTOCOL_VERSION,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.cluster_id:
            headers["mcp-cluster-id"] = self.cluster_id
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def __aenter__(self) -> MCPClient:
        self._client = httpx.AsyncClient(timeout=self._timeout)
        await self._initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        assert self._client is not None
        resp = await self._client.post(self.endpoint, headers=self._headers(), json=body)
        if resp.status_code == 401:
            raise MCPError("MCP authorization failed (401) -- check MCP_API_KEY / scopes")
        resp.raise_for_status()
        return resp

    async def _initialize(self) -> None:
        resp = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": _CLIENT_INFO,
                },
            }
        )
        # The server assigns a session id via response header on init.
        self._session_id = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
        payload = _parse_jsonrpc(resp)
        if "error" in payload:
            raise MCPError(f"initialize failed: {payload['error']}")
        # Complete the handshake (fire-and-forget notification).
        assert self._client is not None
        try:
            await self._client.post(
                self.endpoint,
                headers=self._headers(),
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
        except httpx.HTTPError:
            logger.debug("initialized notification failed (non-fatal)", exc_info=True)

    async def list_tools(self) -> list[dict[str, Any]]:
        resp = await self._post({"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list"})
        payload = _parse_jsonrpc(resp)
        if "error" in payload:
            raise MCPError(f"tools/list failed: {payload['error']}")
        return payload.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        resp = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        payload = _parse_jsonrpc(resp)
        if "error" in payload:
            raise MCPError(f"tools/call({name}) failed: {payload['error']}")
        result = payload.get("result", {})
        # MCP tool results come back as a list of content blocks; surface text.
        content = result.get("content")
        if isinstance(content, list):
            texts = [
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ]
            joined = "\n".join(t for t in texts if t)
            if joined:
                return joined
        return result


def get_mcp_settings() -> tuple[str | None, str | None, str | None]:
    """Return (endpoint, api_key, cluster_id) from Settings; None for anything unset."""
    from app.core.config import get_settings

    s = get_settings()
    return s.MCP_ENDPOINT, s.MCP_API_KEY, s.MCP_CLUSTER_ID


def is_configured() -> bool:
    """Whether the managed MCP server is configured (endpoint + key present)."""
    endpoint, api_key, _ = get_mcp_settings()
    return bool(endpoint and api_key)


def _pick_tool(tools: list[dict[str, Any]], *candidates: str) -> str | None:
    """Choose the first available tool whose name matches one of ``candidates``.

    Names are matched case-insensitively and by substring so we're resilient to
    the managed server's exact tool naming (e.g. ``select_query`` vs ``query``).
    """
    names = [t.get("name", "") for t in tools]
    lowered = {n.lower(): n for n in names}
    for cand in candidates:
        if cand in names:
            return cand
        if cand.lower() in lowered:
            return lowered[cand.lower()]
    for cand in candidates:
        for low, original in lowered.items():
            if cand.lower() in low:
                return original
    return None


async def run_read_query(statement: str) -> str:
    """Execute a read-only SQL ``statement`` via the managed MCP server.

    Returns the tool's text result, or raises ``MCPError``. Callers must ensure
    the statement is read-only; the managed server's ``mcp:read`` scope also
    enforces this server-side.
    """
    endpoint, api_key, cluster_id = get_mcp_settings()
    if not (endpoint and api_key):
        raise MCPError("MCP server not configured (set MCP_ENDPOINT and MCP_API_KEY)")
    async with MCPClient(endpoint, api_key, cluster_id=cluster_id) as mcp:
        tools = await mcp.list_tools()
        tool = _pick_tool(tools, "select_query", "run_query", "query", "sql")
        if tool is None:
            raise MCPError(
                f"No query tool exposed by MCP server; saw: {[t.get('name') for t in tools]}"
            )
        # Different servers name the SQL arg differently; try the common ones.
        last_err: MCPError | None = None
        for arg in ("statement", "sql", "query"):
            try:
                return await mcp.call_tool(tool, {arg: statement})
            except MCPError as exc:
                last_err = exc
                continue
        raise MCPError(f"Could not invoke {tool} with a known argument name: {last_err}")
