"""Conditional-edge routing functions for LangGraph graphs.

Each function inspects graph state and returns the name of the next node
(or ``END``). These are stubs for Week 1+ once the chat graph grows beyond
the linear echo pipeline (e.g. deciding whether to retrieve memories,
whether extracted facts warrant a memory write, etc.).
"""

from typing import Literal

from app.core.graph.state import ChatState, IngestionState


def should_retrieve_memories(state: ChatState) -> Literal["retrieve", "skip"]:
    """Decide whether the chat graph should query the memory engine.

    Will eventually inspect the latest user message / token budget to skip
    retrieval for trivial turns (e.g. greetings) and save latency.
    """
    raise NotImplementedError


def should_write_memory(state: ChatState) -> Literal["write", "skip"]:
    """Decide whether facts extracted from the turn are worth persisting."""
    raise NotImplementedError


def should_check_contradictions(state: IngestionState) -> Literal["check", "skip"]:
    """Decide whether newly extracted claims need contradiction detection."""
    raise NotImplementedError
