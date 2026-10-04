"""Foreground continuation after the real disposition of an acceptance attempt.

No started dependency is rewritten, no old task is reset, no decision is made.
One local effect per call; caller checkpoints before the next operation.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import task_context as tc
import task_create as create
import task_dependencies as dependencies
import task_operation as operations
from acceptance_workflow import AcceptanceWorkflow
from decision_evidence import canonical, line
from quality_policy import feature_digest
from selection_context import file_snapshot


def require(value, code):
    if not value:
        raise tc.ContextError(code)


@dataclass(frozen=True)
class OperationPermission:
    """Host-read permission for one exact action, not proof by construction."""
    request_digest: str
    source_ref: str


@dataclass(frozen=True)
class SuccessorPlan:
    old_task: str
    review_task: str
    task_id: str
    source_digest: str
    decision_digest: str
    argv: tuple
    detail_digest: str
    existing: bool = False


class ReworkWorkflow:
    def __init__(self, root, *, session, authorize=None, repo_overrides=None):
        self.acceptance = AcceptanceWorkflow(root, session=session, repo_overrides=repo_overrides)
        self.root = self.acceptance.root
        self.authorize = authorize
        self.overrides = self.acceptance.overrides

    def _permission(self, action, scope):
        require(callable(self.authorize), 'OPERATION_AUTHORITY_REQUIRED')
        request = dict(feature=self.root.name, root=str(self.root), action=action, scope=scope)
        digest = hashlib.sha256(canonical(request)).hexdigest()
        try:
            permission = self.authorize(deepcopy(request))
        except Exception:
            raise tc.ContextError('OPERATION_AUTHORITY_UNAVAILABLE') from None
        require(type(permission) is OperationPermission and permission.request_digest == digest
                and line(permission.source_ref), 'OPERATION_AUTHORITY_UNVERIFIED')
        return permission

    def preview_successor(self, old_task, review_task, **binding):
        disposition = self.acceptance.verify_disposition(old_task, **binding)
        feature = self.acceptance._feature()
        row, review = feature.records[old_task], feature.records.get(review_task)
        require(review is not None and review['type'] == 'Review', 'SUCCESSOR_REVIEW_REQUIRED')
        old_ancestors, pending = set(), list(row['dependencies'])
        while pending:
            key = pending.pop()
            if key not in old_ancestors:
                old_ancestors.add(key)
                pending.extend(feature.records[key]['dependencies'])
        require(review_task not in old_ancestors, 'NEW_REVIEW_ATTEMPT_REQUIRED')
        detail = feature.details[old_task][0]
        selected = {}
        for label, prefix in (('Requirement points', 'REQ'), ('Solution points', 'SOL')):
            aliases = (label, '需求点' if prefix == 'REQ' else '方案点')
            selected[label] = tc.point_selectors(detail, label, aliases)
            require(tc.point_selectors(feature.details[review_task][0], label, aliases) == selected[label],
                    'SUCCESSOR_SCOPE_MISMATCH')
        product = feature.repositories[binding['candidate_repository']]
        target = feature.type_contracts[review_task].get('Target SHA')
        require(target == product['actual_head'] or (target == '-' and review['state'] == 'PENDING'),
                'SUCCESSOR_TARGET_MISMATCH')
        inputs = ('Acceptance successor of ' + old_task + '; review ' + review_task
                  + '; decision ' + disposition['decision_digest'])
        matches = [key for key, item in feature.records.items()
                   if item['type'] == 'Acceptance' and key != old_task
                   and ('- Inputs: ' + inputs) in feature.details[key][0].splitlines()]
        require(len(matches) <= 1, 'AMBIGUOUS_ACCEPTANCE_SUCCESSOR')
        require(any(repo['actual_head'] == disposition['source_version']
                    for repo in feature.repositories.values() if repo['role'] == 'project-management'),
                'ACCEPTANCE_SOURCE_CHANGED')
        if matches:
            key = matches[0]
            require(feature.records[key]['dependencies'] == [review_task], 'SUCCESSOR_SOURCE_CHANGED')
            fields = feature.type_contracts[key]
            require(fields['Acceptance scope'] == feature.type_contracts[old_task]['Acceptance scope']
                    and (fields['Target SHA'] == target or
                         (fields['Target SHA'] == '-' and feature.records[key]['state'] == 'PENDING')),
                    'SUCCESSOR_SCOPE_MISMATCH')
            for label, prefix in (('Requirement points', 'REQ'), ('Solution points', 'SOL')):
                aliases = (label, '需求点' if prefix == 'REQ' else '方案点')
                require(tc.point_selectors(feature.details[key][0], label, aliases) == selected[label],
                        'SUCCESSOR_SCOPE_MISMATCH')
            return SuccessorPlan(old_task, review_task, key, feature_digest(feature),
                disposition['decision_digest'], (), '', True)
        argv = [str(self.root), '--type', 'Acceptance', '--name', row['name'] + ' successor',
            '--depends-on', review_task, '--goal', 'Request a new decision for the new reviewed candidate',
            '--inputs', inputs, '--work', 'Prepare a new brief after current quality evidence is eligible',
            '--completion-condition', 'Record an actual human decision for this exact new candidate and scope',
            '--resume-action', 'Wait for the new review, then prepare and show the new acceptance brief',
            '--requirement-points', ','.join(selected['Requirement points']) or 'none',
            '--solution-points', ','.join(selected['Solution points']) or 'none',
            '--contract', 'Target SHA=' + target,
            '--contract', 'Acceptance scope=' + feature.type_contracts[old_task]['Acceptance scope']]
        refs = feature.details[old_task][1]
        for ref in refs:
            repo = feature.repositories[ref['repository']]
            argv += ['--repo-ref', '|'.join((ref['repository'], repo['actual_branch'], ref['baseline_history']))]
        args = create.parse_args(argv)
        task_id = create.allocate_task_id(feature.records, 'ACCEPT')
        repo_refs = create.parse_repo_refs(args.repo_ref, tc.repository_registry(feature.documents.read('STATUS.md')))
        contract = create.contract_for('ACCEPT', [review_task], create.parse_contract(args.contract))
        text = create.render_detail(task_id, args, [review_task], selected['Requirement points'],
                                    selected['Solution points'], repo_refs, contract)
        return SuccessorPlan(old_task, review_task, task_id, feature_digest(feature),
            disposition['decision_digest'], tuple(argv), hashlib.sha256(text.encode()).hexdigest())

    def create_successor(self, plan, **binding):
        require(type(plan) is SuccessorPlan, 'INVALID_SUCCESSOR_PLAN')
        current = self.preview_successor(plan.old_task, plan.review_task, **binding)
        if current.existing:
            require(current.task_id == plan.task_id, 'SUCCESSOR_SOURCE_CHANGED')
            return dict(task_id=current.task_id, effect='UNCHANGED', required_next_action='INSPECT_PENDING_DOWNSTREAM',
                        merge_authorized=False)
        require(current == plan, 'SUCCESSOR_SOURCE_CHANGED')
        self._permission('create-acceptance-successor', dict(plan=plan.__dict__))
        require(self.preview_successor(plan.old_task, plan.review_task, **binding) == plan, 'SUCCESSOR_SOURCE_CHANGED')
        before = file_snapshot(self.root)
        def before_write():
            require(file_snapshot(self.root) == before, 'SUCCESSOR_SOURCE_CHANGED')
            # The old acceptance grant proves disposition, not permission to
            # perform this operation now. Re-read after the writer prepares.
            self._permission('create-acceptance-successor', dict(plan=plan.__dict__))
            # Host reads can yield to other editors. Do not publish candidates
            # prepared from stale bytes, or roll back over the editor's work.
            require(file_snapshot(self.root) == before, 'SUCCESSOR_SOURCE_CHANGED')

        # Existing task_create owns its per-file write behavior. A lost effect
        # must be recovered from actual files, never automatically retried here.
        with operations.coordinator(self.root):
            require(file_snapshot(self.root) == before, 'SUCCESSOR_SOURCE_CHANGED')
            task_id = create.create(self.root, create.parse_args(list(plan.argv)), before_write=before_write)
        require(task_id == plan.task_id, 'SUCCESSOR_SOURCE_CHANGED')
        return dict(task_id=task_id, effect='APPLIED_PENDING_CHECKPOINT',
            required_next_action='CHECKPOINT_MANAGEMENT_FILES', merge_authorized=False)

    def rewire_pending(self, old_task, successor_task, downstream_task, *, expected_index_digest,
                       operation_gist, **binding):
        disposition = self.acceptance.verify_disposition(old_task, **binding)
        feature = self.acceptance._feature()
        successor, downstream = feature.records.get(successor_task), feature.records.get(downstream_task)
        require(successor is not None and successor['type'] == 'Acceptance'
                and successor['state'] == 'PENDING', 'PENDING_SUCCESSOR_REQUIRED')
        fields = feature.type_contracts[successor_task]
        require(fields['Decision'] == 'WAITING' and fields['Decided by'] == '-',
                'SUCCESSOR_DECISION_MUST_BE_NEW')
        marker = '- Inputs: Acceptance successor of ' + old_task + '; review '
        origins = [value for value in feature.details[successor_task][0].splitlines() if value.startswith(marker)]
        require(len(origins) == 1 and origins[0].endswith('; decision ' + disposition['decision_digest']),
                'SUCCESSOR_SCOPE_MISMATCH')
        review_id = origins[0][len(marker):].split(';', 1)[0]
        plan = self.preview_successor(old_task, review_id, **binding)
        require(plan.existing and plan.task_id == successor_task, 'SUCCESSOR_SCOPE_MISMATCH')
        require(downstream is not None and downstream['state'] == 'PENDING'
                and old_task in downstream['dependencies'], 'UNSTARTED_DOWNSTREAM_REQUIRED')
        for label, aliases in (('Requirement points', ('Requirement points', '需求点')),
                                ('Solution points', ('Solution points', '方案点'))):
            require(tc.point_selectors(feature.details[successor_task][0], label, aliases)
                    == tc.point_selectors(feature.details[old_task][0], label, aliases),
                    'SUCCESSOR_SCOPE_MISMATCH')
        new_dependencies = [successor_task if value == old_task else value for value in downstream['dependencies']]
        preview = dependencies.plan_dependencies(dependencies.read_source(self.root, 'TASKS.md'),
            dependencies.read_source(self.root, f'tasks/{downstream_task}.md'), downstream_task,
            expected_index_digest, new_dependencies)
        permission = self._permission('rewire-acceptance-successor', dict(old_task=old_task,
            successor_task=successor_task, downstream_task=downstream_task,
            index_digest=expected_index_digest, dependencies=new_dependencies,
            decision_digest=disposition['decision_digest'], source_digest=feature_digest(feature),
            operation_gist=operation_gist, topology_digest=preview['topology_digest']))
        require(self.acceptance.verify_disposition(old_task, **binding) == disposition,
                'ACCEPTANCE_SOURCE_CHANGED')
        require(feature_digest(self.acceptance._feature()) == feature_digest(feature), 'SUCCESSOR_SOURCE_CHANGED')
        return dependencies.replace_dependencies(self.root, downstream_task, expected_index_digest,
            new_dependencies, operation_gist=operation_gist, repo_overrides=self.overrides,
            authority=True, authority_source_ref=permission.source_ref)
