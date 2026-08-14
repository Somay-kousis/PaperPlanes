"""Tests for the memory_introspect tool loop in app.core.nodes.chat.agent_node.

``_run_with_introspection`` drives a bounded model<->tool exchange: the model
may emit ``MemoryIntrospect`` tool calls, each executed as a read-only query via
``mcp_client.run_read_query`` and fed back as a ``ToolMessage``, until the model
answers without a tool call or the iteration cap is hit. These tests use a fake
model (no Bedrock) and a monkeypatched ``run_read_query`` (no MCP server).
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.core.nodes.chat import agent_node
from app.memory import mcp_client


class _FakeBound:
    """A bind_tools() result whose ainvoke replays a scripted response sequence."""

    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)
        self.calls: list[list[Any]] = []

    async def ainvoke(self, convo: list[Any]) -> AIMessage:
        self.calls.append(list(convo))
        return self._responses.pop(0)


class _FakeModel:
    def __init__(self, bound: _FakeBound):
        self._bound = bound
        self.bound_with: Any = None

    def bind_tools(self, tools: list[Any]) -> _FakeBound:
        self.bound_with = tools
        return self._bound


def _tool_call(query: str, call_id: str = "call-1") -> dict[str, Any]:
    return {"name": "MemoryIntrospect", "args": {"query": query}, "id": call_id}


async def test_executes_tool_call_and_feeds_result_back(monkeypatch):
    queries: list[str] = []

    async def fake_run_read_query(q: str) -> str:
        queries.append(q)
        return '{"rows":[{"n":7}]}'

    monkeypatch.setattr(mcp_client, "run_read_query", fake_run_read_query, raising=False)

    bound = _FakeBound(
        [
            AIMessage(content="", tool_calls=[_tool_call("SELECT count(*) FROM x")]),
            AIMessage(content="You have 7 memory notes."),
        ]
    )
    result = await agent_node._run_with_introspection(
        _FakeModel(bound), [HumanMessage("how many?")], None, None
    )

    assert result.content == "You have 7 memory notes."
    assert queries == ["SELECT count(*) FROM x"]
    # Second model call must include the ToolMessage carrying the query result.
    second_convo = bound.calls[1]
    assert any(getattr(m, "content", None) == '{"rows":[{"n":7}]}' for m in second_convo)


async def test_no_tool_call_returns_immediately(monkeypatch):
    called = False

    async def fake_run_read_query(q: str) -> str:
        nonlocal called
        called = True
        return "should not run"

    monkeypatch.setattr(mcp_client, "run_read_query", fake_run_read_query, raising=False)

    bound = _FakeBound([AIMessage(content="Direct answer, no SQL needed.")])
    result = await agent_node._run_with_introspection(
        _FakeModel(bound), [HumanMessage("hi")], None, None
    )

    assert result.content == "Direct answer, no SQL needed."
    assert called is False
    assert len(bound.calls) == 1


async def test_query_failure_is_reported_not_raised(monkeypatch):
    async def failing_run_read_query(q: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        mcp_client, "run_read_query", failing_run_read_query, raising=False
    )

    bound = _FakeBound(
        [
            AIMessage(content="", tool_calls=[_tool_call("SELECT 1")]),
            AIMessage(content="I couldn't read that, but here's what I know."),
        ]
    )
    result = await agent_node._run_with_introspection(
        _FakeModel(bound), [HumanMessage("q")], None, None
    )

    assert result.content == "I couldn't read that, but here's what I know."
    tool_msg = next(m for m in bound.calls[1] if type(m).__name__ == "ToolMessage")
    # The raw SQL/DB error must NOT be handed to the model (it parrots it into
    # the user-facing answer); a neutral fallback instruction is used instead.
    assert "boom" not in tool_msg.content
    assert "could not be queried" in tool_msg.content


async def test_stops_after_max_iters(monkeypatch):
    async def fake_run_read_query(q: str) -> str:
        return "{}"

    monkeypatch.setattr(mcp_client, "run_read_query", fake_run_read_query, raising=False)

    # Model keeps asking for tools forever; loop must cap it and force a final call.
    responses = [
        AIMessage(content="", tool_calls=[_tool_call(f"SELECT {i}", f"c{i}")]) for i in range(10)
    ]
    bound = _FakeBound(responses)
    result = await agent_node._run_with_introspection(
        _FakeModel(bound), [HumanMessage("q")], None, None
    )

    # _MAX_TOOL_ITERS loop invocations + 1 forced final invocation.
    assert len(bound.calls) == agent_node._MAX_TOOL_ITERS + 1
    assert isinstance(result, AIMessage)


def test_addendum_uses_configured_database():
    text = agent_node._introspect_addendum("paperplanes_dev")
    assert "paperplanes_dev.public.memory_notes" in text
    assert "paperplanes_prod" not in text
