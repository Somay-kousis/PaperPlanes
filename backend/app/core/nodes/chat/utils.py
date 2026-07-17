"""Small shared helpers for chat-graph nodes."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


def last_human_text(messages: list[BaseMessage]) -> str:
    """Return the text content of the most recent human message, or ``""``."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""


def last_ai_text(messages: list[BaseMessage]) -> str:
    """Return the text content of the most recent assistant message, or ``""``."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return str(msg.get("content", ""))
    return ""
