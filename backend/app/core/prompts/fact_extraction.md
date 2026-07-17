Extract any durable facts, preferences, or goals the user stated in this
exchange that are worth remembering across future sessions.

Rules:
- Only extract things the USER said or clearly confirmed, not the assistant.
- Skip small talk, one-off requests, and anything already obvious from context.
- Each fact must be a single self-contained sentence, understandable without
  the surrounding conversation.
- If nothing is worth remembering, return an empty list.

Conversation turn:
{turn}

Return a JSON list of objects: {{"content": str, "is_user_stated": true,
"tags": [str, ...], "importance": float between 0 and 1}}.
