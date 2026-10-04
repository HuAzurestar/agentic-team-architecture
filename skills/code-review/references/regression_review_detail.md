# Weak review: compatibility and regression

List each changed existing semantic; “no compatibility problems found” is insufficient without the affected paths and evidence.

## Content points

- Have meanings, defaults, exception types, empty/null handling, ordering or side effects changed?
- Do old APIs, consumers, configuration and workflows still function?
- Are historical schemas/data readable, and is migration safe for existing records?
- Have direct callers, transitive callers, registered entry points and external consumers been considered?
- Are removed symbols truly unused, including plugin, serialization and configuration references?
- Do meaningful historical bug regressions still execute against the new candidate?
- Are generated artifacts, packaging and supported-version assumptions still consistent with the source?
- Are old evidence and accepted behavior valid on the target rather than assumed transferable by branch name?

## Scan and challenge

Follow changed public definitions to consumers and siblings. Try an old input/config/data fixture, omitted values and a historical failure example. Compare old and new behavior using pinned versions where needed. During the initial blind scan, inspect ordinary existing tests but do not load old review conclusions. After freezing the blind report, read the ledger and verify each applicable historical fix; absence from the new findings is not proof of closure.
