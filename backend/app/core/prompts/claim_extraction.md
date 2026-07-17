Extract the substantive factual claims from the excerpt below as
(subject, predicate, object) triples, plus a natural-language restatement
of each claim.

Prioritise, in this order:
1. Quantitative results the paper reports about a method, system, or
   dataset (a system reaching some score on some benchmark, a model of
   some size, a measured latency, and so on).
2. Comparative findings (one method outperforming, matching, or
   underperforming another).
3. Other checkable assertions the paper makes as its own finding.

Read the numbers and comparisons FROM THE EXCERPT ITSELF. Never copy the
illustrative wording of these instructions -- if the excerpt states a
particular percentage, parameter count, or ranking, use exactly that
value, not any figure mentioned here.

Extract EVERY distinct claim of these kinds in the excerpt, not just the
first or the most prominent one. A short excerpt can still contain
several claims -- do not stop after one.

For "subject", strongly prefer the actual system, method, model, or
dataset the claim is about, NOT the paper itself. When the excerpt reports
a result about a named system (even one another paper introduced), the
subject is that system, not the current paper's title. Only use the paper
as the subject when the claim is genuinely about the paper as an artifact
(for instance, a paper introducing a new benchmark) and there is no better
subject. Avoid vacuous self-description claims such as "this paper is a
reproduction study" or "this paper benchmarks agents".

Only extract claims the paper asserts as true or as its own finding or
result -- not claims it merely attributes to prior work as something it
disputes, unless you make that explicit in the statement.

Known entities in this paper (use these exact names for "subject"/
"object" whenever the claim refers to one of them):
{entities}

Excerpt:
{chunk_text}

Return claims as a JSON list of objects with keys "subject" (str, an
entity name from the list above, or the studied system/method/dataset the
claim is about), "predicate" (str, a short verb phrase, e.g. "achieves",
"uses", "outperforms", "introduces"), "object" (str -- either one of the
known entity names above, or a scalar value taken verbatim from the excerpt, such as a
percentage or a parameter count), "statement" (str, a self-contained
natural-language sentence
restating the claim, including the specific numbers or comparison so it is
checkable on its own), and "confidence" (float between 0 and 1). Skip
anything that isn't a clear, checkable claim.
