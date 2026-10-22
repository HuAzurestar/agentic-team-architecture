# Runtime persistence: project management and notification bindings

The included `scripts/runtime_state.py` implements local configuration persistence with explicit --state-root and --runtime-id arguments. The host must supply these arguments through a supported runtime binding; no Multica daemon loader is installed by this helper.

## Local helper usage

The host passes an absolute state directory and runtime identity on every call. Copy and fill the two templates first; they are intentionally invalid until explicit values are supplied. PyYAML is the existing package dependency.

```text
python <skill-root>/scripts/runtime_state.py --state-root <absolute-state-directory> --runtime-id <runtime-id> configure --kind project-management --input <filled-project-management.yaml>
python <skill-root>/scripts/runtime_state.py --state-root <absolute-state-directory> --runtime-id <runtime-id> configure --kind notification --input <filled-notification.yaml>
python <skill-root>/scripts/runtime_state.py --state-root <absolute-state-directory> --runtime-id <runtime-id> resolve --kind project-management
```

`configure` retains immutable revisions and compares an existing revision using `--expected-revision`. Repeating identical configuration is idempotent; changing content requires a new revision. Conflicting writes fail explicitly instead of waiting or retrying. `resolve` checks structure and runtime identity; its locator output does not prove filesystem/network access or action authority.

For project-management profiles, fill `management roots` as name-to-absolute-path, `selected root` as an existing key, `project registry` as an absolute path, and the state-writer/commit-policy references as nonempty strings. Environment references remain a mapping. For notification profiles, adapter tool reference, failure handling reference and reply correlation contract are nonempty strings, routes/event bindings are mappings, credentials are string references and delivery state reference is an absolute directory. These are data, never executable shell commands.

## Ownership and bootstrap

Agent instructions express the user's organization and authority. They must not contain machine paths, runtime IDs, endpoints, credentials or per-machine notification tool names. The development machine/runtime owns this skill's persistent configuration; moving an agent selects the destination runtime's configuration rather than editing its instructions.

The runtime supplies one explicit, readable skill-state locator through its supported bootstrap/tool binding. Do not resolve this locator from the PM root (which it must itself locate), an agent ID, a repository scan or a guessed home directory. Packaging the same skill does not imply runtimes share state. Skill installation, this locator, and writable state access must all be checked. If unavailable, report the missing bootstrap, do no dependent IO, and continue independent analysis. This helper adds no daemon feature, undocumented environment variable or automatic loader.

Keep two independent, runtime-scoped persistent profiles outside the replaceable installed skill package:

1. `project-management.yaml`: profile/revision, runtime identity, named PM root mappings and explicit selector, stable Project registry location, state-write access, authorized commit policy and non-secret environment references.
2. `notification.yaml`: profile/revision, runtime identity, adapter/tool reference, routes and credential references, workflow-event bindings, delivery-state location, reply correlation and authorized failure handling.

Names are relative filenames inside the runtime-supplied state locator, not mandatory global filesystem locations. Templates are examples with null values, never activated defaults. Organization/approval policy is a separate versioned input; a tool binding cannot grant authority.

## Project-management configuration IO

Input: explicit runtime identity/state locator, authorized setup or change request, exact PM mapping and selected profile. Optional: existing repository and environment mappings. Setup persists validated supplied facts; daily work reads and reuses them. Do not choose among ambiguous roots or initialize/migrate/clone repositories implicitly.

Output: resolved PM/Project/environment access plus profile revision, verification scope and missing/conflicting items. Separate locator syntax, actual access and authorization. Stable Project mappings remain at `project/<project-key>/project.yaml`; Feature design/tasks remain at the PM root. Runtime state does not become another Feature status ledger.

Machine-specific repository/environment overrides belong to the runtime profile; logical repository identity and shared project rules remain in Project definitions. A permanent mapping change requires explicit scope, retained revision, affected-task assessment and normal record validation. Credentials remain references. Concurrent writers must reconcile, not overwrite.

## Notification configuration IO

Input: explicit runtime/state profile, runtime-provided adapter/tool, routes, receiving-system contract and authorized delivery rules. Output: persisted profile revision and verified capabilities/limitations; never claim delivery or callback support from configuration alone.

Notification events and acknowledgements use the configured durable transport state. Formal decisions and useful execution evidence still belong in PM tasks/design. See [notification hooks](notification-hooks.md) for event IO. Notification configuration can be unavailable while unrelated PM/read-only work proceeds; inability to resolve one profile must not cause a guessed fallback to the other.

## Migration and recovery experiment

Move the same agent instructions from runtime A to B. B resolves its own explicit profiles, PM mapping and adapter. Check shared repository identity, access and current candidate before writes. Do not transfer A's endpoints/secrets implicitly. Existing PM state remains authoritative; pending deliveries/requests require an explicit ownership handoff and correlation check before replay. Compare profile revisions and reject stale replies for other object revisions. Successful migration does not imply old callbacks or remote permissions moved.

## Storage and interruption boundary

Each profile retains immutable history in `history/<kind>/<revision>.yaml` plus a `<revision>.parent.json` predecessor sidecar. An interrupted update can retry the same revision only from its recorded predecessor; old revisions cannot be reused as a rollback. A state-root conflict lock fails explicitly. A stale lock is not stolen automatically: inspect the recorded operation/process and establish it has ended before a human or authorized host removes the lock. Atomic replace protects completed file writes; this is not a claim of zero-loss recovery after arbitrary power loss.
