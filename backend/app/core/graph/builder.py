"""Graph construction for the chat and paper-ingestion pipelines.

``build_chat_graph`` is ``load_context -> retrieve -> assemble_context ->
agent -> write_episodes -> extract_facts -> memory_write -> END``. Every
node from ``retrieve`` onward self-degrades (no AWS creds, no retrievable
chunks/notes, an invocation error, an unreachable DB) rather than
requiring the caller to branch between "real" and "echo" graphs, so this
one compiled graph covers every environment from CI (no AWS/DB) to full
production RAG + memory. ``write_episodes``/``extract_facts``/
``memory_write`` all run *after* the reply is already in ``state`` --
their job is to durably record the turn and consolidate any facts worth
remembering, never to affect what the user sees.

``build_ingestion_graph`` is the paper-ingestion pipeline:
``fetch -> parse -> chunk -> embed -> store_chunks -> extract_entities ->
extract_claims -> contradiction_check -> mark_ready -> END``, with
conditional edges (through ``store_chunks``) that short-circuit straight
to ``mark_ready`` (which writes ``papers.status = 'failed'``) the moment
any step reports failure via ``state["status"] == "failed"``. The last
three steps -- entity/claim extraction and contradiction-checking -- are
wired as plain (unconditional) edges instead: each one self-degrades on a
prior failure (checks ``state["status"] == "failed"`` and no-ops) exactly
like ``store_chunks_node``/``embed_node`` do, so a paper still reaches
``mark_ready`` (and 'ready', if nothing failed upstream) even if no
AWS credentials are configured or a single chunk's extraction call fails.
"""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.core.graph.state import ChatState, IngestionState
from app.core.nodes.chat.agent_node import agent_node
from app.core.nodes.chat.assemble_context_node import assemble_context_node
from app.core.nodes.chat.extract_facts_node import extract_facts_node
from app.core.nodes.chat.load_context_node import load_context_node
from app.core.nodes.chat.memory_write_node import memory_write_node
from app.core.nodes.chat.retrieve_node import retrieve_node
from app.core.nodes.chat.write_episodes_node import write_episodes_node
from app.core.nodes.ingestion.chunk_node import chunk_node
from app.core.nodes.ingestion.contradiction_check_node import contradiction_check_node
from app.core.nodes.ingestion.embed_node import embed_node
from app.core.nodes.ingestion.extract_claims_node import extract_claims_node
from app.core.nodes.ingestion.extract_entities_node import extract_entities_node
from app.core.nodes.ingestion.fetch_node import fetch_node
from app.core.nodes.ingestion.mark_ready_node import mark_ready_node
from app.core.nodes.ingestion.parse_node import parse_node
from app.core.nodes.ingestion.store_chunks_node import store_chunks_node


def build_chat_graph(checkpointer: Any | None = None) -> Any:
    """Build and compile the chat graph.

    ``checkpointer`` should be an ``AsyncCockroachDBSaver`` (see
    ``app.memory.db.checkpointer.get_checkpointer``) for persisted
    conversations, or ``None`` to compile without persistence -- used as
    a fallback when the database is unavailable.
    """
    graph = StateGraph(ChatState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("assemble_context", assemble_context_node)
    graph.add_node("agent", agent_node)
    graph.add_node("write_episodes", write_episodes_node)
    graph.add_node("extract_facts", extract_facts_node)
    graph.add_node("memory_write", memory_write_node)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "retrieve")
    graph.add_edge("retrieve", "assemble_context")
    graph.add_edge("assemble_context", "agent")
    graph.add_edge("agent", "write_episodes")
    graph.add_edge("write_episodes", "extract_facts")
    graph.add_edge("extract_facts", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile(checkpointer=checkpointer)


def _continue_or_fail(state: IngestionState) -> Literal["continue", "fail"]:
    """Route to ``mark_ready`` early if a prior ingestion step failed."""
    return "fail" if state.get("status") == "failed" else "continue"


def build_ingestion_graph(checkpointer: Any | None = None) -> Any:
    """Build and compile the paper-ingestion graph.

    ``fetch -> parse -> chunk -> embed -> store_chunks -> mark_ready``.
    Every step but the last routes through ``_continue_or_fail``: a step
    that sets ``state["status"] = "failed"`` (with ``fail_reason``) jumps
    straight to ``mark_ready``, which persists that failure to
    ``papers.status``/``papers.fail_reason`` instead of running the
    remaining steps.
    """
    graph = StateGraph(IngestionState)
    graph.add_node("fetch", fetch_node)
    graph.add_node("parse", parse_node)
    graph.add_node("chunk", chunk_node)
    graph.add_node("embed", embed_node)
    graph.add_node("store_chunks", store_chunks_node)
    graph.add_node("extract_entities", extract_entities_node)
    graph.add_node("extract_claims", extract_claims_node)
    graph.add_node("contradiction_check", contradiction_check_node)
    graph.add_node("mark_ready", mark_ready_node)

    graph.add_edge(START, "fetch")
    graph.add_conditional_edges(
        "fetch", _continue_or_fail, {"continue": "parse", "fail": "mark_ready"}
    )
    graph.add_conditional_edges(
        "parse", _continue_or_fail, {"continue": "chunk", "fail": "mark_ready"}
    )
    graph.add_conditional_edges(
        "chunk", _continue_or_fail, {"continue": "embed", "fail": "mark_ready"}
    )
    graph.add_conditional_edges(
        "embed", _continue_or_fail, {"continue": "store_chunks", "fail": "mark_ready"}
    )
    graph.add_edge("store_chunks", "extract_entities")
    graph.add_edge("extract_entities", "extract_claims")
    graph.add_edge("extract_claims", "contradiction_check")
    graph.add_edge("contradiction_check", "mark_ready")
    graph.add_edge("mark_ready", END)

    return graph.compile(checkpointer=checkpointer)
