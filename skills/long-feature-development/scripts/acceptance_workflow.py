"""Acceptance host entry: retained originals, prepared metadata, guarded writer.

The host supplies identity readers. No CLI option authenticates a person.
Metadata preparation and the management checkpoint remain explicit operations.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from context_loader import LocalMarkdownLoader, load_feature
import task_context as tc
import task_state as writer
import state_prepared as prepared
import decision_host as human
import quality_source as sources
from decision_evidence import decision_digest
from state_acceptance import AcceptanceReader


def require(value, code):
    if not value:
        raise tc.ContextError(code)


class AcceptanceWorkflow:
    def __init__(self, root, *, session=None, repo_overrides=None):
        self.root = Path(root).resolve(strict=True)
        self.session = session
        self.overrides = dict(repo_overrides or {})

    def _feature(self):
        return tc.validate_feature(load_feature(LocalMarkdownLoader(self.root)),
                                   tc.LocalGitProbe(self.root, self.overrides))

    def inspect(self, task_id):
        """Read the actual frozen attempt; never interpret a reply or record it."""
        feature = self._feature()
        row = feature.records.get(task_id)
        require(row is not None and row['type'] == 'Acceptance', 'ACCEPTANCE_TASK_REQUIRED')
        fields = feature.type_contracts[task_id]
        return dict(task_id=task_id, state=row['state'], dependencies=list(row['dependencies']),
            target_sha=fields.get('Target SHA'), acceptance_scope=fields.get('Acceptance scope'),
            brief=fields.get('Acceptance brief'), decision=fields.get('Decision'),
            effect='NOT_APPLIED', merge_authorized=False,
            required_next_action=('READ_ACTUAL_HUMAN_DECISION'
                if row['state'] in {'WIP', 'BLOCKED'} else 'FOLLOW_RETAINED_ATTEMPT'))

    def prepare(self, args, changes):
        """Bind exact planned bytes while the full baseline is still clean.

        The caller then prepares ONLY these detail/STATUS bytes. This function
        neither writes those files nor derives a decision from the plan.
        """
        require(Path(args.feature_directory).resolve(strict=True) == self.root
                and args.task_id.startswith('ACCEPT-')
                and args.to in {'RECORDING', 'DONE'}, 'ACCEPTANCE_DECISION_TRANSITION_REQUIRED')
        return prepared.PreparedTransition(self.root, args, changes, repo_overrides=self.overrides)

    def verify_disposition(self, task_id, *, decision_path, candidate_repository, exact_scope):
        """Read an actual completed negative decision for its frozen old attempt.

        The current product may have advanced: this does not accept that product
        or release it. Scope/source bindings come from the configured caller.
        """
        feature = self._feature()
        row = feature.records.get(task_id)
        require(row is not None and row['type'] == 'Acceptance' and row['state'] == 'DONE',
                'ACCEPTANCE_DISPOSITION_REQUIRED')
        fields = feature.type_contracts[task_id]
        require(fields['Decision'] in {'REJECTED', 'REWORK'}, 'NEGATIVE_DISPOSITION_REQUIRED')
        require(type(exact_scope) is tuple and 0 < len(exact_scope) <= 1000
                and all(isinstance(item, str) for item in exact_scope), 'INVALID_DECISION_SCOPE')
        session = self.session
        require(session is not None and getattr(session, 'feature', None) == self.root.name
                and isinstance(getattr(session, 'source_key', None), str)
                and all(callable(getattr(session, name, None))
                        for name in ('read_reply', 'interpret', 'read_grant')),
                'HUMAN_SOURCE_UNAVAILABLE')
        detail = feature.documents.read(f'tasks/{task_id}.md')
        declared = set(tc.declared_gist_names(detail))
        brief = fields.get('Acceptance brief')
        require(brief in declared and decision_path in declared and decision_path != brief,
                'ACCEPTANCE_SOURCE_NOT_DECLARED')
        owners = [repo for repo in feature.repositories.values()
                  if repo['role'] == 'project-management' and self.root.is_relative_to(Path(repo['path']))]
        require(len(owners) == 1, 'INVALID_DECISION_SOURCE')
        owner = owners[0]
        repository = Path(owner['path']).resolve(strict=True)
        documents = tuple(sources.GitDocument(path, repository,
            (self.root / path).relative_to(repository).as_posix(), owner['actual_head'])
            for path in (decision_path, brief))
        product = feature.repositories.get(candidate_repository)
        require(product is not None and product['role'] != 'project-management'
                and tc.commit_exists(Path(product['path']), fields['Target SHA']),
                'ACCEPTANCE_TARGET_MISMATCH')
        snapshot = sources.read_git_documents(documents)
        record = snapshot.object(decision_path, 'decision-evidence-v1')
        require(record.get('outcome') == fields['Decision']
                and record.get('actor') == fields['Decided by']
                and record.get('exact_scope') == list(exact_scope), 'ACCEPTANCE_SCOPE_CHANGED')
        current = dict(feature=self.root.name, decision_kind='acceptance',
            target_ref=dict(source_key=session.source_key, version_kind='git', version=fields['Target SHA']),
            exact_scope=list(exact_scope),
            body=snapshot.documents[brief].decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'))
        from review_resume import _markdown
        versions = [line for kind, _, line in _markdown(current['body'])
                    if kind == 'line' and re.match(r'^(?:Target version|目标版本)[:：]', line)]
        require(len(versions) == 1 and re.fullmatch(r'(?:Target version|目标版本)[:：]\s*`?'
            + re.escape(fields['Target SHA']) + r'`?\s*', versions[0]), 'ACCEPTANCE_TARGET_MISMATCH')
        def read_current():
            require(sources.read_git_documents(documents) == snapshot, 'ACCEPTANCE_SOURCE_CHANGED')
            return deepcopy(current)
        def source_call(method, *args):
            try:
                return method(*args)
            except Exception:
                raise tc.ContextError('HUMAN_SOURCE_UNAVAILABLE') from None
        grant = deepcopy(source_call(session.read_grant, None, deepcopy(record)))
        result = human.inspect_decision(record, read_current=read_current,
            read_reply=lambda ref: source_call(session.read_reply, ref),
            interpret=lambda reply, raw: source_call(session.interpret, reply, raw), grant=grant)
        require(result['applicable'] and result['source_verified'],
                result['reason_codes'][0] if result['reason_codes'] else 'HUMAN_SOURCE_UNVERIFIED')
        require(source_call(session.read_grant, None, deepcopy(record)) == grant, 'HUMAN_AUTHORITY_CHANGED')
        read_current()
        after = self._feature()
        require(after.documents.read_set == feature.documents.read_set
                and after.repositories == feature.repositories, 'ACCEPTANCE_SOURCE_CHANGED')
        return dict(task_id=task_id, outcome=fields['Decision'], target_sha=fields['Target SHA'],
            scope=list(exact_scope), decision_digest=decision_digest(record),
            source_version=owner['actual_head'], merge_authorized=False)

    def record(self, preparation, *, decision_document, candidate_repository, exact_scope):
        """Explicitly record one actual decision; no commit, new attempt or merge.

        On an exception or process loss inspect physical files and recover before
        any further write; this entry does not retry a possibly completed effect.
        """
        require(type(preparation) is prepared.PreparedTransition
                and preparation.root == self.root and preparation.overrides == self.overrides,
                'INVALID_STATE_PREPARATION')
        args = deepcopy(preparation.args)
        require(Path(args.feature_directory).resolve(strict=True) == self.root
                and args.task_id == preparation.request.task_id
                and args.to == preparation.request.target
                and args.to in {'RECORDING', 'DONE'}, 'STATE_PREPARATION_MISMATCH')
        session = self.session
        require(session is not None and getattr(session, 'feature', None) == self.root.name
                and isinstance(getattr(session, 'source_key', None), str)
                and all(callable(getattr(session, name, None))
                        for name in ('read_reply', 'interpret', 'read_grant')),
                'HUMAN_SOURCE_UNAVAILABLE')
        reader = AcceptanceReader(preparation, decision_document=decision_document,
            candidate_repository=candidate_repository, source_key=session.source_key,
            exact_scope=exact_scope, read_reply=session.read_reply,
            interpret=session.interpret, read_grant=session.read_grant)
        candidate = writer.update(self.root, args, evidence_reader=reader)
        require(candidate == preparation.candidate, 'STATE_PREPARATION_MISMATCH')
        row = tc.task_records(candidate)[args.task_id]
        return dict(task_id=args.task_id, state=row['state'],
            effect='NOT_APPLIED' if args.dry_run else 'APPLIED_PENDING_CHECKPOINT',
            index_digest=hashlib.sha256(candidate.encode('utf-8')).hexdigest(),
            required_next_action='PREPARE_AND_RECORD' if args.dry_run else 'CHECKPOINT_MANAGEMENT_FILES',
            merge_authorized=False, publication_performed=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect a retained acceptance attempt without recording a decision.')
    parser.add_argument('feature_directory')
    parser.add_argument('task_id')
    parser.add_argument('--repo', action='append', default=[], metavar='NAME=PATH')
    args = parser.parse_args(argv)
    try:
        result = AcceptanceWorkflow(args.feature_directory,
            repo_overrides=tc.parse_repo_overrides(args.repo)).inspect(args.task_id)
        code = 0
    except Exception:
        result, code = dict(effect='NOT_APPLIED', reason_codes=['ACCEPTANCE_CONTEXT_UNAVAILABLE'],
            required_next_action='CHECK_RETAINED_ATTEMPT_AND_CONTEXT', merge_authorized=False), 2
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
