# F01 walkthrough cards, AC01 through AC06

These cards exercise the documentation produced by PIRC-31/DEV-F01-02. They are expected walkthroughs, not executed product test results. TEST-F01-01 must record its actual environment, observations, and results separately.

| Case | Given and action | Expected observable result |
| --- | --- | --- |
| F01-AC01 | Beacon has Git, supported Python, and an explicit Markdown root; SMMD is absent and service use is forbidden. Apply the selection in [runtime](../../docs/long-feature/runtime.md). | Choose Skill only; `task_context.py` uses the local root and real Git refs. Neither SMMD nor Docker appears in the required steps. Missing Python/root is reported as a named gap. |
| F01-AC02 | Apply Git first, provider first, and hybrid separately to the same `BEACON-PLAN` in [authority routing](authority-routing.md). | Every variant names one editing source and labels its snapshot and replicas. The hybrid decision document has its own source; no row asks for two way sync. |
| F01-AC03 | Read the two `OPS-7` refs in [authority routing](authority-routing.md), then follow its relative links to management and recovery. | The two tasks differ by repository identity and full SHA. Relative links resolve in this checkout. The fictional remote refs are identified as examples and must be verified before a real handoff. |
| F01-AC04 | Use [recovery](recovery.md) with save and commit successful, push response unknown, provider publication failed. | Four separate results remain. The next step for push is an exact ref query; the next step for the provider is an exact object/revision query. Neither write is blindly replayed. |
| F01-AC05 | Only SMMD v1 is installed. Request Skill plus SMMD features that depend on F08 conditional writes and F13 same source context. | Compatibility is unverified and the missing version/capability is named. A health response does not allow a combined route; complete Skill only execution remains available if its own prerequisites hold. |
| F01-AC06 | For each of the four routes in [runtime](../../docs/long-feature/runtime.md), locate program/config owner, text/history owner, backup, upgrade, and exit. | Every route keeps source data on exit. No route deletes a source as an uninstall step. The delivered [F02 directory installation guide](../../skills/long-feature-development/references/installation.md) covers Skill-only setup; actual SMMD installation and combined acceptance remain PIRC-34/F15 work and are not implied by that guide. |

The references in these cards are local relative paths. A real test report should record each link check and mark a missing target as failure rather than rewriting the claim to a plain label.
