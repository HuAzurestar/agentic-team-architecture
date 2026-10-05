"""Skill-only foreground host for point, review, acceptance and rework entries.

Bind capabilities in trusted host code. Standalone invocation has no principal,
permission, plugin loader or decision inference; readable routes remain usable.
"""
import argparse
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import task_context as context
import decision_workflow as points
import review_workflow as reviews
import acceptance_workflow as acceptance
import quality_host as quality
from rework_workflow import ReworkWorkflow


class FeatureHost:
    def __init__(self, root, *, point_sessions=None, acceptance_session=None,
                 review_options=None, authorize=None, read_provenance=None, repo_overrides=None):
        self.root = Path(root).resolve(strict=True)
        self.overrides = dict(repo_overrides or {})
        self.point_sessions = dict(point_sessions or {})
        if not set(self.point_sessions) <= {'REQ', 'SOL'}:
            raise context.ContextError('INVALID_HOST_POINT_BINDINGS')
        self.acceptance_session = acceptance_session
        self.review_options = dict(review_options or {})
        if set(self.review_options) - {'git_binding', 'endpoint', 'repository', 'operation_gist', 'authorize'}:
            raise context.ContextError('INVALID_HOST_REVIEW_BINDINGS')
        self.authorize, self.read_provenance = authorize, read_provenance

    def point(self, point_id):
        prefix = point_id.split('-', 1)[0]
        return points.PointWorkflow(self.root, session=self.point_sessions.get(prefix),
                                    repo_overrides=self.overrides)

    def review(self):
        return reviews.ReviewWorkflow(self.root, repo_overrides=self.overrides, **self.review_options)

    def acceptance(self):
        return acceptance.AcceptanceWorkflow(self.root, session=self.acceptance_session,
                                              repo_overrides=self.overrides)

    def rework(self):
        return ReworkWorkflow(self.root, session=self.acceptance_session,
                              authorize=self.authorize, repo_overrides=self.overrides)

    def assess_quality(self, config_bytes):
        inputs = quality.configured_inputs(self.root, config_bytes, self.overrides)
        return quality.evaluate(self.root, **inputs, read_provenance=self.read_provenance)


def main(argv=None, *, host=None):
    parser = argparse.ArgumentParser(description='Run one foreground long-feature workflow; no background scheduler.')
    parser.add_argument('feature_directory')
    parser.add_argument('action', choices=('context', 'point', 'review', 'acceptance', 'quality'))
    args, rest = parser.parse_known_args(argv)
    try:
        root = Path(args.feature_directory).resolve(strict=True)
        if host is None:
            host = FeatureHost(root)
        if type(host) is not FeatureHost or host.root != root:
            raise context.ContextError('HOST_FEATURE_MISMATCH')
        # Repository overrides are host-owned when embedding. Forward them to
        # legacy read-only CLIs, but never override a configured host binding.
        overrides = [part for name, path in host.overrides.items() for part in ('--repo', name + '=' + str(path))]
        if host.overrides and any(value == '--repo' or value.startswith('--repo=') for value in rest):
            raise context.ContextError('HOST_REPOSITORY_OVERRIDE_CONFLICT')
        forwarded = [str(root), *rest, *overrides]
        if args.action == 'context':
            return context.main(forwarded)
        if args.action == 'point':
            if not rest or rest[0].startswith('-'):
                raise context.ContextError('POINT_SCOPE_REQUIRED')
            session = host.point(rest[0]).session
            return points.main(forwarded, session=session)
        if args.action == 'review':
            # A configured host source takes precedence; unbound standalone
            # users can select the registered read-only Git route in that CLI.
            workflow = host.review() if host.review_options else None
            return reviews.main(forwarded, workflow=workflow)
        if args.action == 'acceptance':
            return acceptance.main(forwarded)
        return quality.main(forwarded, read_provenance=host.read_provenance)
    except Exception:
        print('{"effect":"NOT_APPLIED","reason_codes":["HOST_WORKFLOW_UNAVAILABLE"],'
              '"required_next_action":"CHECK_HOST_BINDINGS_AND_FEATURE_CONTEXT","merge_authorized":false}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
