# Weak review: core

For each point, search the actual delta and sibling implementations. Retain evidence or an explicit unknown/N/A reason; emit findings, not a questionnaire score.

## Content points

- Can the main feature be stated in 1–3 sentences and each major change mapped to an agreed requirement?
- Are required behaviors missing, unrequested additions present, or product semantics changed without a decision?
- Is each capability reuse, adaptation or new work, with existing-code evidence?
- Do new tables, states, frameworks and abstractions solve a current problem that existing mechanisms cannot handle?
- Does each module have a coherent responsibility and appropriate layer? Are rules scattered across unrelated modules?
- Are dependency direction, cycles and knowledge of other modules' internals consistent with the project?
- Do public helpers/services already provide the new computation, validation, mapping or serialization?
- Are there exact duplicates, different-looking semantic duplicates, intentional duplication or shared mechanisms that need consistency?
- Are new symbols unused or replaced old paths, unreachable branches, abandoned flags and commented historical implementations left behind?
- Would middleware/interceptors/decorators for authorization, logging, retries, context, validation, transactions or error translation reduce demonstrated cross-cutting inconsistency now?

## Scan and challenge

Map requirements to changed modules. Trace added/changed definitions, callers and sibling helpers. Search semantic equivalents, not only names: available amount can also be total minus consumed. Test a required scenario omitted from the author's happy path. Inspect all consumers of a repeated rule before proposing a shared mechanism.

Do not infer dead code merely from a missing textual reference: check registration, reflection, plugins, configuration and entry points. Do not demand abstraction just because two local expressions resemble each other. Explain the concrete maintenance/behavioral consequence.
