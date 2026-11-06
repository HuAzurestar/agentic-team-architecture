# Generated indexes and protected sections

Read when initializing an index layout, refreshing previews/topology/attachments, or investigating generated-content drift.

## Fixed locations

Each document keeps its Feature title and short introduction. Put each marker pair on standalone lines directly after the specified H2 heading, with only blank lines between heading and start marker. Keep each pair unique, ordered and within that section.

| Document | H2 section | Generated region name | Source |
| --- | --- | --- | --- |
| DESIGN.md | preview-table | design-preview-table | design/*.md YAML |
| TASKS.md | preview-table | tasks-preview-table | tasks/*.md YAML |
| TASKS.md | dependency-topology | tasks-dependency-topology-mermaid | Task IDs, titles, states and depends on |
| VERBAL.md | preview-table | verbal-preview-table | Actual files under gists/ |

A region uses `<!-- name:start -->` and `<!-- name:end -->`. Do not edit the contents by hand. Keep manual, dated notes under `## complementary` after the generated sections; titles, introductions and notes are outside script ownership. Design/task facts still belong to their detailed records, not duplicate index ledgers.

Fenced Markdown examples may repeat these headings and markers; they do not count as real sections or generated regions and are preserved verbatim. Real duplicate headings or markers outside fences remain errors. A region found only inside an example is not a usable generation target.

Do not wrap tables or sections in standalone horizontal rules. Only YAML frontmatter keeps its delimiter lines; Markdown table header separators remain necessary table syntax.

## Generate and update

As required by [SKILL.md](../SKILL.md), synchronize through the [index generator](../scripts/feature_indexes.py) after every content/state operation, then run record checking; this is not optional cleanup. The agent authors content using templates; scripts do not create new SOL content, task judgments or decisions:

```text
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --check
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --write
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --only tasks --write
python "<skill-root>/scripts/feature_indexes.py" "<feature-directory>" --only verbal --write
```

Resolve the absolute script and Feature paths as defined in [SKILL.md](../SKILL.md#required-maintenance-for-each-operation); the current directory need not be the skill root. The default is read-only check mode. A stale index returns nonzero; --write explicitly replaces only the generated region bodies. --only tasks updates both the task table and topology. Edit the source detail or attachment tree, then run the generator; do not paste a hand-maintained table or diagram into a generated block.

--write belongs to the index generator and permits derived-region writes only, not business bodies. --format json/text belongs to the record checker and selects its report representation. The generator always reports JSON and has no --format option; none of these flags is a content-authoring mode. Synchronization here means derived indexes within files, not automatic Git pull/push or remote synchronization.

The task graph includes isolated tasks and points from each dependency to its consumer. It describes dependencies, not an additional lifecycle or a mandated company workflow. Unknown dependencies and cycles are rejected from the task records before generation.

The attachment index lists relative paths, byte sizes and filesystem modification times in UTC. It does not read file content or invent descriptions, creation times, retention policies or approval status. Symlink entries are not followed. An incomplete scan is an error, not an empty successful result.

VERBAL/gists remains disposable: missing gists produces an empty attachment table; a missing VERBAL is skipped by all-mode and is not recreated. An explicit --only verbal requires that index file. The formal Feature checker never depends on this attachment index or its current contents.

## Safety and repair

All selected targets and generated spans are prepared before any write. Missing, duplicated, reversed, inline or misplaced markers, crossing sections, invalid source records and incomplete attachment scans fail preflight. The generator does not invent missing headings or replace an entire document to repair its layout. Re-establish only the intended headings/markers outside generated content, preserve other text, then rerun.

Unmanaged content is retained byte-for-byte, including UTF-8 BOM and line endings. Identical outputs are not rewritten. Output files must be direct non-symlink files in the selected Feature. Per-file replacements are atomic and check for concurrent changes; this is not a cross-file transaction or a replacement for the state maintainer's write coordination. After an interrupted/concurrent update, inspect the result and rerun check rather than assuming all files changed.

Neither generation nor structural checking mutates detail YAML, STATUS, Project configuration or attachment content. No commit, network call, scheduling or approval is implied. The [record checker](../scripts/contract_check.py) checks formal preview/topology agreement; --render design/tasks/topology remains a stdout-only diagnostic.

Implementation boundaries are in [index_blocks.py](../scripts/index_blocks.py) (`scripts/index_blocks.py` from the skill root); behavior tests are in [test_feature_indexes.py](../scripts/test_feature_indexes.py). The supplied templates already include valid fixed sections.
