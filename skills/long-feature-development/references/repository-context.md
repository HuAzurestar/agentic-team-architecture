# Repository identity, observed points and integration context

Read when locating a Project checkout, comparing recorded and actual code state, or preparing integration/review/PR handoff. Repository topology and Git/forge policy come from the project; this reference defines the facts to preserve.

## Resolve identity before operating

Resolve project key through its stable project.yaml and the caller's device/OS mapping. A historical local path is a hint, not proof of repository identity. Confirm the intended checkout and remote identity using available read-only evidence. Do not operate on an ambiguous or mismatched checkout, clone/move it automatically, or silently rewrite the Project configuration.

The Project resolver supplies configured locations only. It does not prove that the checkout exists, a remote is current, a commit exists or a shortened SHA is unique.

## Keep reference meanings distinct

When applicable, record these as specialized task metadata, with an overall repository status in STATUS rather than a duplicate detailed registry:

| Fact | Meaning |
| --- | --- |
| Working area and observed HEAD | The Project-qualified branch area and literal commit point actually used for this attempt. |
| Integration opponent | The exact branch/point used as merge or rebase input, not a moving alias substituted for the prior input. |
| PR/MR source and target | The review/merge endpoints and their observed points; they can differ from the local working HEAD and integration opponent. |

A multi-Project task identifies each Project's points separately; equal branch names do not identify equal repositories. Use project@SHA for frozen points and project@branch for areas, as defined in [protocol.md](protocol.md#points-and-areas). Do not label one generic current SHA as all three facts.

## Compare without rewriting history

Inspect relevant local refs, dirty changes and, when available/authorized, remote observations. Compare recorded and observed points before mutating code or claiming existing test/review/acceptance applies. Where workflow depends on ancestry or dependency integration, verify it in the actual Repository; the structural checker does not do this.

If a branch or PR moves, retain the previously reviewed/tested point and record the new observation separately. Determine what work or approval must be repeated rather than rewriting an old report's target. Unavailable remote/CI/forge state stays unverified, not guessed current.

An unrequested merge, push, deployment or remote mutation is not a consequence of resolving references. Follow the external project policy; this skill imposes neither a fixed integration-branch count nor a fixed PR count.
