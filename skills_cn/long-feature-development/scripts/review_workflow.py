"""Foreground review workflow for agent/workbench callers and read-only CLI."""
import argparse
from dataclasses import dataclass
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from context_loader import LocalMarkdownLoader, load_feature
import task_context as tc
import task_operation as operations
from decision_evidence import canonical, line
import review_source as git_source
import review_native as native
import review_publish as git_publish
import review_native_publish as native_publish
import review_sync as sync
from review_application import assess_application


class WorkflowError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise WorkflowError(code)


@dataclass(frozen=True)
class ReviewPermission:
    """Host permission bound to a request digest, never read from review content."""
    request_digest: str
    source_ref: str


class ReviewWorkflow:
    def __init__(self, root, *, git_binding=None, endpoint=None, repository=None,
                 operation_gist=None, authorize=None, repo_overrides=None):
        self.root = Path(root).resolve(strict=True)
        require(git_binding is None or endpoint is None, 'AMBIGUOUS_REVIEW_SOURCE')
        require(endpoint is None or type(endpoint) is native.NativeDocument, 'INVALID_REVIEW_BINDING')
        self.binding = deepcopy(git_binding)
        self.endpoint = endpoint
        self.repository, self.gist = repository, operation_gist
        self.authorize, self.overrides = authorize, dict(repo_overrides or {})
        if endpoint is not None:
            require(endpoint.feature == self.root.name, 'REVIEW_FEATURE_MISMATCH')
        if git_binding is not None:
            require(type(git_binding) is dict and git_binding.get('feature') == self.root.name,
                    'REVIEW_FEATURE_MISMATCH')

    def read(self, purpose='review', *, explicit_review=False, statuses=None, rv_ids=None):
        options = dict(explicit_review=explicit_review, statuses=statuses, rv_ids=rv_ids)
        if self.endpoint is not None:
            return native.read_for_purpose(purpose, endpoint=self.endpoint, **options)
        return git_source.read_for_purpose(purpose, git_binding=self.binding, **options)

    def _permission(self, action, scope):
        require(callable(self.authorize) and self.gist is not None, 'REVIEW_AUTHORITY_REQUIRED')
        if self.endpoint is not None:
            identity = native_publish._identity(self.endpoint)
        else:
            require(self.binding is not None and self.repository is not None, 'REVIEW_NOT_BOUND')
            identity = {key: str(value) for key, value in self.binding.items()}
        request = dict(action=action, feature=self.root.name, root=str(self.root),
                       source=identity, operation_gist=self.gist, scope=scope)
        digest = hashlib.sha256(canonical(request)).hexdigest()
        try:
            permit = self.authorize(deepcopy(request))
        except Exception:
            raise WorkflowError('REVIEW_AUTHORITY_UNAVAILABLE') from None
        require(type(permit) is ReviewPermission and permit.request_digest == digest
                and line(permit.source_ref), 'REVIEW_AUTHORITY_UNVERIFIED')
        return permit

    def prepare_publication(self, draft, *, observation=None, supersedes=None):
        # Keep selected UI filters out of the write baseline: publication always
        # binds the complete authoritative original and all three review states.
        require(isinstance(draft, str), 'INVALID_REVIEW_DRAFT')
        observed = observation if observation is not None else self.read(statuses=git_publish.STATES)
        scope = dict(source_version=observed['source_version'], source_digest=observed['source_digest'],
                     draft_digest=hashlib.sha256(draft.encode('utf-8')).hexdigest(), supersedes=supersedes)
        permit = self._permission('prepare-review-publication', scope)
        if self.endpoint is not None:
            return native_publish.prepare(self.root, self.gist, self.endpoint, observed, draft,
                permit.source_ref, self.overrides, authority=True, supersedes=supersedes)
        return git_publish.prepare(self.root, self.gist, self.repository, self.binding, observed, draft,
            permit.source_ref, self.overrides, authority=True, supersedes=supersedes)

    def publish(self, operation_id, intent_digest):
        self._publication_record(operation_id, intent_digest)
        self._permission('publish-review', dict(operation_id=operation_id, intent_digest=intent_digest))
        if self.endpoint is not None:
            return native_publish.execute(self.root, self.gist, operation_id, self.endpoint, self.overrides,
                                           authority=True, expected_intent_digest=intent_digest)
        return git_publish.execute(self.root, self.gist, operation_id, self.overrides,
                                    authority=True, expected_intent_digest=intent_digest)

    def inspect_publication(self, operation_id):
        self._publication_record(operation_id)
        if self.endpoint is not None:
            return native_publish.reconcile(self.root, self.gist, operation_id, self.overrides, False, self.endpoint)
        return git_publish.reconcile(self.root, self.gist, operation_id, self.overrides, False)

    def _publication_record(self, operation_id, intent_digest=None):
        require(self.gist is not None, 'REVIEW_JOURNAL_REQUIRED')
        record = operations.read_gist(self.root, self.gist)[3][operation_id]
        require(record['feature'] == self.root.name, 'REVIEW_FEATURE_MISMATCH')
        if self.endpoint is not None:
            require(record['kind'] == native_publish.KIND, 'REVIEW_SOURCE_MISMATCH')
            native_publish._validate(self.endpoint, record)
        else:
            require(self.binding is not None and record['kind'] == 'review-publish'
                    and record['target_identity']['repository'] == self.repository
                    and record['expected_source']['binding'] == {key: value for key, value in self.binding.items() if key != 'repo'},
                    'REVIEW_SOURCE_MISMATCH')
        require(intent_digest is None or git_publish.intent_digest(record) == intent_digest,
                'REVIEW_INTENT_CHANGED')
        return record

    def preflight(self, observation, *, expected_working_head, expected_branch, samples):
        require(self.binding is not None and self.endpoint is None, 'GIT_REVIEW_SOURCE_REQUIRED')
        permit = self._permission('apply-review', dict(source_version=observation['source_version'],
            source_digest=observation['source_digest'], working_head=expected_working_head,
            working_branch=expected_branch, rv_ids=[item['rv_id'] for item in observation['records']]))
        return assess_application(self.binding, observation, expected_working_head=expected_working_head,
            expected_branch=expected_branch, samples=samples, authorized=True, authority_source_ref=permit.source_ref)

    def prepare_master_sync(self, observation):
        require(self.binding is not None and self.endpoint is None, 'GIT_REVIEW_SOURCE_REQUIRED')
        permit = self._permission('prepare-review-master-sync', dict(source_version=observation['source_version'],
            source_digest=observation['source_digest']))
        operation_id = sync.prepare(self.root, self.gist, self.repository, self.binding, observation,
                                     permit.source_ref, self.overrides, authority=True)
        record = operations.read_gist(self.root, self.gist)[3][operation_id]
        return dict(operation_id=operation_id, intent_digest=git_publish.intent_digest(record))

    def synchronize_master(self, operation_id, intent_digest):
        require(self.binding is not None and self.endpoint is None, 'GIT_REVIEW_SOURCE_REQUIRED')
        record = operations.read_gist(self.root, self.gist)[3][operation_id]
        require(record['kind'] == 'review-master-sync'
                and record['target_identity']['repository'] == self.repository
                and record['expected_source']['review_binding'] == {key: value for key, value in self.binding.items() if key != 'repo'}
                and git_publish.intent_digest(record) == intent_digest, 'REVIEW_INTENT_CHANGED')
        self._permission('synchronize-review-master', dict(operation_id=operation_id, intent_digest=intent_digest))
        # The existing sync owns the durable dispatch and management/implementation
        # distinctions. Reentry does not repeat an unknown merge.
        return sync.execute(self.root, self.gist, operation_id, self.overrides, authority=True)


def permission_digest(request):
    """Binding helper for an actual host authorization reader; not a grant."""
    return hashlib.sha256(canonical(request)).hexdigest()


def main(argv=None, *, workflow=None):
    parser = argparse.ArgumentParser(description='Read authoritative reviews in the foreground.')
    parser.add_argument('feature_directory')
    parser.add_argument('--repository', help='Registered repository for a Git-backed source')
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--review-path', default='REVIEWS.md')
    parser.add_argument('--review-ref', help='Logical source ref, default REPOSITORY:PATH')
    parser.add_argument('--purpose', default='review', choices=('requirement', 'solution', 'development', 'review', 'delivery'))
    parser.add_argument('--explicit-review', action='store_true')
    parser.add_argument('--status', action='append', choices=('PENDING', 'ADDRESSED', 'VERIFIED'))
    parser.add_argument('--rv-id', action='append')
    parser.add_argument('--repo', action='append', default=[], metavar='NAME=PATH')
    args = parser.parse_args(argv)
    try:
        root = Path(args.feature_directory).resolve(strict=True)
        if workflow is None:
            overrides = tc.parse_repo_overrides(args.repo)
            binding = None
            if args.repository is not None:
                feature = tc.validate_feature(load_feature(LocalMarkdownLoader(root)), tc.LocalGitProbe(root, overrides))
                repo = feature.repositories[args.repository]
                binding = dict(repo=Path(repo['path']), remote=args.remote, expected_remote=repo['remote'],
                    repository_ref=args.repository, relative_path=args.review_path, feature=root.name,
                    reviews_ref=args.review_ref or args.repository + ':' + args.review_path)
            workflow = ReviewWorkflow(root, git_binding=binding, repository=args.repository, repo_overrides=overrides)
        require(type(workflow) is ReviewWorkflow and workflow.root == root, 'REVIEW_FEATURE_MISMATCH')
        result = workflow.read(args.purpose, explicit_review=args.explicit_review, statuses=args.status, rv_ids=args.rv_id)
        code = 0
    except Exception:
        result, code = dict(status='ERROR', read_executed=False, reason_codes=['REVIEW_SOURCE_UNAVAILABLE'],
                            agent_consumed=False), 2
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
