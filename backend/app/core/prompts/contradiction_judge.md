You are checking whether two claims, drawn from different papers,
genuinely contradict each other.

Claim A:
{claim_a}

Claim B:
{claim_b}

Consider: different scope/conditions, different time periods, different
datasets or baselines, or different subjects can make two claims appear
contradictory while both are true. Only flag a real logical
contradiction -- if one claim merely refines, extends, restates, or is
silent on something the other covers, that is not a contradiction.

Return exactly one relation:
- "contradicts": the two claims cannot both be true as stated.
- "supports": the two claims reinforce or restate the same finding.
- "unrelated": the two claims are about different things, or there isn't
  enough overlap to judge either way.

Return JSON with keys "relation" (one of the three strings above) and
"rationale" (str, one or two sentences explaining the judgment).
