# Beacon: three authority strategies

Beacon is a fictional project. These records illustrate choices, not existing repositories or platform objects. In every variant, `BEACON-PLAN` is the same ordinary Markdown plan with the same content. Only its editing authority changes. Do not combine the variants into one live register.

| Strategy | Environment/project | Document | Source | Provider condition and original evidence | Replicas | Maintainer | Rule ref |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Git first | Beacon/staging | `BEACON-PLAN` | `https://github.com/example/beacon-api.git`, `project/BEACON-PLAN.md` | Before edit: full source commit and file hash | Git commit snapshot; provider object `beacon:plan` is a separately published copy | Beacon project owner | `PIRC-31/SOL-001`, Git first |
| Provider first | Beacon/staging | `BEACON-PLAN` | provider `beacon-docs`, exact object `beacon:plan` | Observed native revision `r17`; if the provider cannot condition an update, use its explicit human edit flow | Exported `project/BEACON-PLAN.md` in the repo is a read only copy | Beacon project owner | `PIRC-31/SOL-001`, provider first |
| Hybrid | Beacon/staging | `BEACON-PLAN` | `https://github.com/example/beacon-api.git`, `project/BEACON-PLAN.md` | Before edit: full source commit and file hash | Provider object `beacon:plan` is a copy | Beacon project owner | `PIRC-31/SOL-001`, hybrid plan row |
| Hybrid | Beacon/staging | `BEACON-DECISION` | provider `beacon-docs`, exact object `beacon:decision` | Observed native revision `r9`; require a supported conditional update or explicit human edit | Exported `project/BEACON-DECISION.md` is a copy | Beacon project owner | `PIRC-31/SOL-001`, hybrid decision row |

For the Git first and hybrid plan rows, save to the declared repository path, inspect its diff, commit only the intended files, then publish the provider copy only after its target is confirmed. For provider first, edit `beacon:plan` with its native condition and export a new read only copy after the edit. Exporting never changes the source. For hybrid, the plan and decision have different sources; neither document has two sources.

## Same task ID in two repositories

The following illustrative refs identify two different `OPS-7` tasks. They are data examples, not clickable claims about live commits:

| Task | Complete ref | Why it is distinct |
| --- | --- | --- |
| API work | `https://github.com/example/beacon-api.git@0123456789abcdef0123456789abcdef01234567:project/OPS-7/TASKS.md#OPS-7` | Repository identity is `beacon-api.git`. |
| UI work | `https://github.com/example/beacon-ui.git@89abcdef0123456789abcdef0123456789abcdef:project/OPS-7/TASKS.md#OPS-7` | Repository identity is `beacon-ui.git`. |

`OPS-7@0123456` is insufficient. A real handoff checks the remote identity, that the full commit exists in that repository, and that the path and task anchor exist at that commit. Only then may a receiver link to the reviewed object. The relative links in this example to [management rules](../../docs/long-feature/management.md) and [recovery](recovery.md) are within this repository and can be checked without inventing live remote objects.

If someone edits both `project/BEACON-PLAN.md` and `beacon:plan` as authorities, stop and record a source switch decision. A timestamp comparison cannot resolve that conflict.
