# Review behavior replay — coordinator only

This is a synthetic, local forward-test packet for PIRC-39 AC01–AC03, AC05 and AC15. It models the relevant failure classes, not the actual PIRC-31/35/38 implementation or their acceptance. It is not part of the skill's default loaded instructions. An audit/structure check or the fixture tests passing is not evidence that an Agent found the issues.

Before review, provide only the requested skill, the literal candidate commit, a scope below, and `original/INPUT.md` plus `original/candidate.py`. Do NOT provide this README, the oracle, the Issue, execution summaries or another mode's report. Use fresh authorized contexts for each mode/case. Do not automatically delegate or create sessions. Evaluation reports go to isolated temporary directories, never the implementation worktree.

Suggested cases:

| Case | Scope | What to measure after the blind report is saved |
| --- | --- | --- |
| Default standalone | no scope configuration | Applicable coverage and justified N/A, without requiring long-feature records |
| Strong full | `review/v1 mode=strong` | Read no weak detail; run useful counterexamples and trace sibling paths |
| Weak full | `review/v1 mode=weak` | Load selected detail only, shared finding format and severity/score |
| Strong core/API | `review/v1 mode=strong topics=core,api exclude=ui` | Topic-scoped exploration and disclosed exclusions |
| Weak core/API | `review/v1 mode=weak topics=core,api exclude=ui` | Only core/API references; no UI report or silent scope expansion |

After freezing a target-bound blind report, compare actual findings with the four seeded defect instances: delivery declarations accepted without required conditions; lost cash in a duplicate cycle; 100 empty internal-ID inputs despite available metadata; restricted contents returned through the shared single-export/download path. Multiple locations of the last instance should not artificially inflate its count. Prioritize by demonstrated consequence, not by a fixed expected severity label. The explicit public-summary contract, denied package export and preserved unrelated cash are negative controls, not new defects by themselves.

Record found/missed instances, unsupported findings, actual counterexamples, read references, the deduplication basis, counts/score, completeness and limits. Scope-limited candidates may detect cross-topic facts while mapping requirements, but must not claim those excluded topics were comprehensively reviewed. Successful static analysis of generated HTML does not claim a rendered browser usability trial. Do not adjust seed behavior merely to make a model test pass.

Run `python -B -X utf8 scripts/tests/run_tests.py --skill review` as the coordinator to establish that the seeded behavior and controls are present. The five fixture tests intentionally observe flawed outputs; their OK result only validates the evaluation fixture, not the candidate or review skill. They are separate from the four scoring tests. The live products and final human acceptance remain unverified. This entire test directory is excluded from skill assembly.
