# Long feature runtime routes

This guide chooses a route for a long running Markdown and Git project. Record the environment facts before choosing a route. A route describes how to work with existing material; it does not install a service or grant access.

The Skill-only candidate uses Python 3.12. Author regressions have been run with CPython 3.12.10 on Windows/NTFS and CPython 3.12.15 on Linux. Other Python versions, macOS and other filesystems are unverified, not implicitly supported by those results. Run `python --version` and `git --version` before setup, record the actual interpreter and pinned product SHA, then follow the [installation checks](../../skills/long-feature-development/references/installation.md). Git must be available on PATH.

## Selection record

Fill in `project`, the authoritative Markdown root, Git repository and remote, host and Python version, whether a local service and containers are permitted, installed SMMD version and capabilities, and whether a same source C3 adapter/profile is available. Mark unknown facts `unknown` and ask the owner; an unknown permission is not permission to start a service. Keep the selected document authority strategy in [management.md](management.md) separate from this runtime choice.

Choose the least set of components that meets the requested work:

| Route | Entry conditions and required components | Optional components | If a condition is missing |
| --- | --- | --- | --- |
| Skill only | Host can run the declared supported Python, Git is available, and the project has an explicit local Markdown entry and repository identity. Use the existing `skills/long-feature-development/scripts/task_context.py` against that root. | An environment maintenance tool may help with setup. | Report the missing Python, Git, root, or repository identity. SMMD and Docker are not prerequisites. |
| SMMD local | A permitted local process, persistent config, controlled source, and a verified SMMD release with the required document capabilities. | Git history for a Git backed source. | A read capability or health response alone does not establish safe write support. Use read only access until the precise write contract is verified. |
| SMMD Docker | All local route conditions, container permission, and an explicit persistent configuration and source mount. | The Skill for task execution. | A missing mount is a blocking setup gap; do not create an empty substitute source in the container. |
| Skill plus SMMD | The Skill only conditions, a verified compatible SMMD release, and a C3 adapter/profile for the same authoritative source. | Container hosting if separately permitted. | Without the adapter or required SMMD feature, use the complete Skill only route for task execution; never splice a partial service projection into local context. |

The current SMMD v1 by itself does not establish F08 conditional writes or F13 same source context exchange. Ask for the actual version and capability response. An installation or health result cannot substitute for a compatibility check. The public [C1/C2/C3 package](../../examples/long-feature/contracts/v0.2-draft/README.md) is present, including its static checker and fixtures. Passing that package is not evidence that an actual combined installation is compatible: validate the precise component versions, same-source adapter and required runtime capabilities separately.

## Data, upgrade, and exit

| Route | Program and config owner | Authoritative text and history | Upgrade and exit |
| --- | --- | --- | --- |
| Skill only | Host's Skill installation and Python environment; project owner controls its repository path. | Project Markdown root and Git history, as declared in the management table. | Save/checkpoint owned changes, record the exact Skill and Git refs, then replace the Skill version. To exit, stop invoking the Skill; retain the Markdown and Git repository. |
| SMMD local | Operator controls process, `providers.json`, credential references, and its data directory. | The configured binding points at the declared source; backups and logs are distinct from the source. | Stop writes, back up the config and source according to their owners, record the version, and test the new version against the existing binding. To exit, stop the process and retain the source and backups. Unbinding is not source deletion. |
| SMMD Docker | Operator controls container image and explicit persistent config/source mounts. | The host mounted source and its owner remain authoritative; a container layer is not a backup. | Record image digest and mount mapping before replacement. Stop the container to exit; keep the mounted data and backups. |
| Skill plus SMMD | Each component keeps its own program/config owner. | Both readers must point to the same declared source. The Skill's execution result still comes from the original Markdown and real Git checks. | Record both versions, source mapping, and contract version; upgrade one component at a time and recheck compatibility. If SMMD is unavailable, return to a complete local read of the same source. |

For a pinned Skill-only installation, use the [directory installation and lifecycle guide](../../skills/long-feature-development/references/installation.md). It provides the existing explicit-root/host-directory routes without SMMD or UI; it does not add an installer service. The context and installation tests exercise real copies and fresh processes. Host discovery and full recovery/review acceptance require their own observations. Actual SMMD installation and combined acceptance belong to PIRC-34/F15. The examples in [F01 scenarios](../../examples/long-feature/f01-scenarios.md) are walkthroughs, not evidence of an installed product.

For every route, the operator owns recovery copies of its actual source and config. Never delete or overwrite user data as part of a route change. Verify a backup can be read before relying on it. Keep credentials in their configured secret source, never in the selection record.
