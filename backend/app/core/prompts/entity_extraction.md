Identify named entities in the following paper excerpt: the paper itself,
its authors, key concepts/topics it discusses, methods/algorithms it uses
or proposes, datasets it uses or introduces, and metrics it reports.

For each entity, give its canonical name and its type (exactly one of:
`paper`, `author`, `concept`, `method`, `dataset`, `metric`), plus any
aliases used in the excerpt (abbreviations, alternate spellings,
alternate names for the same thing).

Excerpt:
{chunk_text}

Return entities as a JSON list of objects with keys "name" (str), "type"
(str, one of the six types above), and "aliases" (list of str, may be
empty). Only extract things you are reasonably confident are genuine
named entities -- skip vague or generic phrases.
