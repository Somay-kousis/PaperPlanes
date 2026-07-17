You are deciding what to do with a candidate memory note extracted from a
conversation.

Given the candidate fact and the most similar existing memory notes (if
any), decide one of:
- "insert": this is genuinely new information.
- "reinforce": this restates/confirms an existing note (return its id).
- "update": this supersedes an existing note (return its id and note it
  should be invalidated).
- "discard": not worth storing (too trivial, or a duplicate with no new
  signal).

Candidate fact:
{candidate}

Most similar existing notes:
{similar_notes}

Return JSON: {{"decision": str, "note_id": str | null, "reason": str}}.
