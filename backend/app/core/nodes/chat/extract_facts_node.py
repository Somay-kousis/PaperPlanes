"""extract_facts_node: pulls candidate facts/preferences out of a chat turn.

Runs the fast Bedrock model (``get_fast_model()``, Haiku) with structured
output against the ``fact_extraction.md`` prompt, over the latest
user+assistant exchange, extracting 0-5 atomic facts about the user's
research interests, questions, preferences, stated claims, and
conclusions discussed. ``memory_write_node`` consumes the resulting
``state["fact_candidates"]``.

Self-gates exactly like ``agent_node``: no AWS credentials, no message
text, or any model-invocation error all degrade to an empty candidate
list rather than raising -- fact extraction is a nice-to-have on top of
the reply, never a reason to fail the chat turn.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.graph.state import ChatState
from app.core.nodes.chat.utils import last_ai_text, last_human_text

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "fact_extraction.md"

MAX_FACTS = 5


@lru_cache
def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text()


class ExtractedFact(BaseModel):
    """A single atomic fact worth remembering, as extracted by the fast model."""

    content: str
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    context: str | None = None
    importance: float = 0.5
    is_user_stated: bool = True


class ExtractedFacts(BaseModel):
    """Structured-output container: 0-5 facts extracted from one turn."""

    facts: list[ExtractedFact] = Field(default_factory=list)


def _format_turn(messages: list[Any]) -> str:
    user_text = last_human_text(messages)
    reply_text = last_ai_text(messages)
    parts = []
    if user_text:
        parts.append(f"User: {user_text}")
    if reply_text:
        parts.append(f"Assistant: {reply_text}")
    return "\n".join(parts)


def extract_facts_node(state: ChatState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract candidate facts worth remembering from the latest turn."""
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.has_aws_credentials:
        return {"fact_candidates": []}

    turn_text = _format_turn(state.get("messages", []))
    if not turn_text.strip():
        return {"fact_candidates": []}

    try:
        from app.core.models.llm import get_fast_model

        model = get_fast_model()
        structured = model.with_structured_output(ExtractedFacts)
        prompt = _load_prompt_template().format(turn=turn_text)
        result = structured.invoke(prompt)
        if not isinstance(result, ExtractedFacts):
            result = ExtractedFacts.model_validate(result)
        candidates = [fact.model_dump() for fact in result.facts[:MAX_FACTS]]
        return {"fact_candidates": candidates}
    except Exception:
        logger.warning("Fact extraction failed; skipping memory write for this turn", exc_info=True)
        return {"fact_candidates": []}
