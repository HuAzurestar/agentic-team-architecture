"""Point decision entry for a configured host, CLI, or workbench caller."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from context_loader import LocalMarkdownLoader, load_feature
import task_context as tc
import decision_host as human
import decision_source as source
from decision_evidence import MAX_BYTES, Invalid, canonical, decision_digest
from decision_commit import CommitError
from point_workflow import run_point
from review_resume import _object


class PointWorkflow:
    """Resolve actual management Git independently from a decision's assertions.

    session is trusted host code with feature/source_key and fresh read_reply,
    interpret/read_grant methods. It may be NativeDecisionSession or a platform
    conversation adapter. No code, credential or permission is imported by CLI.
    """
    def __init__(self, root, *, session, repo_overrides=None):
        self.root = Path(root).resolve(strict=True)
        self.overrides = dict(repo_overrides or {})
        if (session is None or getattr(session, 'feature', None) != self.root.name
                or not all(callable(getattr(session, name, None))
                           for name in ('read_reply', 'interpret', 'read_grant'))
                or not isinstance(getattr(session, 'source_key', None), str)):
            raise human.HostFailure('HUMAN_SOURCE_UNAVAILABLE')
        self.session = session

    def _feature(self):
        return tc.validate_feature(load_feature(LocalMarkdownLoader(self.root)),
                                    tc.LocalGitProbe(self.root, self.overrides))

    def _binding(self, point_id, record):
        decision_digest(record)
        if record['feature'] != self.root.name or record['decision_kind'] != 'point' or record['exact_scope'] != [point_id]:
            raise human.HostFailure('POINT_SCOPE_MISMATCH')
        if record['target_ref']['source_key'] != self.session.source_key:
            raise human.HostFailure('POINT_SOURCE_MISMATCH')
        feature = self._feature()
        if point_id not in feature.records or feature.records[point_id]['type'] not in ('Requirement', 'Solution'):
            raise human.HostFailure('POINT_SCOPE_MISMATCH')
        owners = [repo for repo in feature.repositories.values()
                  if repo['role'] == 'project-management' and self.root.is_relative_to(Path(repo['path']))]
        if len(owners) != 1:
            raise human.HostFailure('POINT_REPOSITORY_MISMATCH')
        repo = Path(owners[0]['path']).resolve(strict=True)
        document = 'REQUIREMENT.md' if point_id.startswith('REQ-') else 'SOLUTION.md'
        return repo, (self.root / document).relative_to(repo).as_posix(), owners[0]['actual_head']

    def inspect(self, point_id, record):
        record = json.loads(canonical(record))
        repo, path, head = self._binding(point_id, record)
        def current():
            return source.read_git_current(repo, path, source_key=self.session.source_key,
                feature=self.root.name, decision_kind='point', exact_scope=[point_id], expected_head=head)
        grant = self.session.read_grant(None, deepcopy(record))
        result = human.inspect_decision(record, read_current=current,
            read_reply=self.session.read_reply, interpret=self.session.interpret, grant=grant)
        if self.session.read_grant(None, deepcopy(record)) != grant:
            raise human.HostFailure('HUMAN_AUTHORITY_CHANGED')
        current()
        self._feature()
        return result

    def apply(self, point_id, record, *, next_status=None, recorded_at=None):
        record = json.loads(canonical(record))
        repo, _, _ = self._binding(point_id, record)
        return run_point(self.root, repo, point_id, record, source_key=self.session.source_key,
            read_reply=self.session.read_reply, interpret=self.session.interpret,
            read_grant=self.session.read_grant, repo_overrides=self.overrides,
            next_status=next_status, recorded_at=recorded_at)


def render(result):
    phase = result.get('phase', 'APPLICABLE' if result.get('applicable') else 'BLOCKED')
    lines = ['Decision: ' + phase]
    for code in result.get('reason_codes', []):
        lines.append('- ' + code)
    action = result.get('required_next_action')
    if action and action != 'NONE':
        lines.append('Next: ' + action)
    for blocker in result.get('blockers', []):
        lines.append('- ' + blocker['task_id'] + ': ' + blocker['state'] + ' depends on ' + blocker['dependency'])
    for key in ('decision_commit', 'status_commit'):
        if result.get(key):
            lines.append(key.replace('_', ' ') + ': ' + result[key])
    difference = result.get('diff')
    if difference:
        lines.extend(['', 'Changed approved material:', json.dumps(difference, ensure_ascii=True)])
    return '\n'.join(lines)


def main(argv=None, *, session=None):
    parser = argparse.ArgumentParser(description='Inspect or apply one decision using a host-configured human source.')
    parser.add_argument('feature_directory')
    parser.add_argument('point_id')
    parser.add_argument('--decision', required=True, help='decision-evidence-v1 record; contains no authority')
    parser.add_argument('--apply', action='store_true', help='Explicitly apply and record; default only inspects')
    parser.add_argument('--repo', action='append', default=[], metavar='NAME=PATH')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    args = parser.parse_args(argv)
    try:
        path = Path(args.decision).absolute()
        reader = LocalMarkdownLoader(path.parent.resolve(strict=True))
        raw, identity = reader._read_raw(path.name, MAX_BYTES)
        record = _object(raw.decode('utf-8-sig'), 'decision-evidence-v1')
        operation = PointWorkflow(args.feature_directory, session=session,
                                   repo_overrides=tc.parse_repo_overrides(args.repo))
        # Freeze caller input before invoking a writer. The writer snapshots and
        # repeatedly verifies the copied decision and actual target thereafter.
        if reader._read_raw(path.name, len(raw)) != (raw, identity):
            raise human.HostFailure('POINT_DECISION_CHANGED')
        result = operation.apply(args.point_id, record) if args.apply else operation.inspect(args.point_id, record)
        code = 0 if result.get('complete') or result.get('applicable') else 1
    except (human.HostFailure, tc.ContextError, CommitError, source.SourceError, Invalid) as error:
        # Only known literal reasons are returned; source content stays private.
        code, result = 2, dict(phase='BLOCKED', complete=False, reason_codes=['WORKFLOW_UNAVAILABLE'],
                              required_next_action='CHECK_SOURCE_AND_CONTEXT')
        if type(error) in (human.HostFailure, CommitError, source.SourceError, Invalid) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,100}', str(error)):
            result['reason_codes'] = [str(error)]
    except Exception:
        code, result = 2, dict(phase='BLOCKED', complete=False, reason_codes=['WORKFLOW_UNAVAILABLE'],
                              required_next_action='CHECK_SOURCE_AND_CONTEXT')
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')) if args.format == 'json' else render(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
