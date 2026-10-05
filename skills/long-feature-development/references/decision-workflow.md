# Decision workflow entry

Use `decision_workflow.PointWorkflow(feature_directory, session=host_session)`
for one explicitly selected REQ/SOL decision. `inspect(point_id, record)` reads
the actual current document and human source, returning applicability and the
changed-span diff. `apply(point_id, record)` creates/applies the decision commit
and records its exact SHA in a following task-status commit. The management
repository is resolved from the feature registry. Completed reentry is read-only;
unknown dispatch uses the retained refs and does not repeat the write.

The CLI is embeddable with `decision_workflow.main(argv, session=session)`:

```text
FEATURE SOL-001 --decision /path/to/decision.json --format text
FEATURE SOL-001 --decision /path/to/decision.json --apply --format json
```

The first command only inspects. The second explicitly requests application.
The JSON record is decision-evidence-v1 and supplies no permission. Standalone
execution without a host session returns HUMAN_SOURCE_UNAVAILABLE. A workbench
or agent host binds the session in its entry script, using its existing secret
store and independently configured message/policy routes; no plugin path,
credential or authority flag is imported from the decision file or CLI.

## Native message and authorization sources

`decision_native.NativeDecisionSession` implements the host session using two
existing `review_native.NativeDocument` bindings: `message` and `authorization`.
Both belong to the same feature/provider and have distinct source refs and URLs.
Bind HTTPS endpoints that serve UTF-8 JSON as text/plain, identity encoding,
and a strong ETag. GET uses the existing bounded native transport. Local HTTP is
available only with the explicit loopback option for development fixtures.

The message service authenticates the original author's identity and retains
their unmodified text and timestamp. It serves this complete object:

```json
{
  "schema": "human-message-v1",
  "source_ref": "provider:message/42",
  "actor": "provider:user/7",
  "actor_kind": "human",
  "received_at": "2026-10-03T12:00:00Z",
  "text": "The actual original reply",
  "interpretations": [
    {"decision_digest": "whole decision record digest", "basis_ref": "host:interpretation/42"}
  ]
}
```

Interpretations are supplied by the host's confirmed understanding of that
actual reply and quoted material. A digest binds the complete decision record;
it does not understand natural language. Broad approval must not produce entries
for unenumerated points. An ambiguous reply has no applicable interpretation
until clarified. This adapter reads the service's interpretation instead of
creating one from the uploaded record.

The separately configured permission service serves:

```json
{
  "schema": "human-authorization-v1",
  "grants": [
    {"actor": "provider:user/7", "feature": "FEATURE", "decision_kind": "point",
     "source_key": "pm:solution", "exact_scope": ["SOL-001"],
     "outcomes": ["CONFIRMED", "REJECTED", "REOPENED"]}
  ]
}
```

An empty outcomes list revokes that grant. Missing, duplicated, malformed or
wrong-actor/feature/source/scope entries deny application. Every grant request
reads current server policy; messages and their interpretation are read again
by the decision gateway. Edited messages change the native ETag. Credentials
remain in NativeDocument host headers, and service errors are reduced to reason
codes. A file using either schema is not an authorization service: trust comes
from the host-configured transport and service ACLs. Deploying these endpoints
and mapping a platform's identities are runtime integration responsibilities.

For an already prepared acceptance transition,
`session.acceptance_reader(preparation, decision_document=...,
candidate_repository=..., exact_scope=...)` supplies the existing protected task
writer's evidence callback. Rejection/rework can be recorded without releasing
the candidate. The actual declared brief and product SHA remain independently
checked by AcceptanceReader.

## Reopening a consumed point

If an assigned task depends on the point, application returns
DEPENDENCY_COORDINATION_REQUIRED with each consumer's ID, state and dependency.
The caller presents those attempts for disposition and uses the existing
controlled dependency/rework flow before trying application again. An in-flight
acceptance requires its actual decision or explicit attempt disposition;
completion must never be fabricated. The point remains unchanged until this
coordination permits a valid task graph.

The focused integration check is `test_decision_workflow.py`. It uses an actual
loopback message/policy service and disposable Git repositories, exercising
revoked permission, two-commit application and completed CLI reentry. Its
identity service is synthetic; production account verification and broad
cross-platform coverage belong to the later review.
