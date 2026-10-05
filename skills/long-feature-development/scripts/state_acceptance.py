"""Actual acceptance originals + prepared-state writer + configured human host.

No uploaded actor or constructor authenticates a user. The host owns reply,
interpretation and current grant readers; this adapter never imports them.
"""
from copy import deepcopy
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import task_context as tc
import state_guard as guard
import state_prepared as prepared
import quality_source as sources
import decision_host as human
from decision_evidence import MAX_BYTES


def require(value, code):
    if not value:
        raise tc.ContextError(code)


class AcceptanceReader:
    def __init__(self, preparation, *, decision_document, candidate_repository,
                 source_key, exact_scope, read_reply, interpret, read_grant):
        require(type(preparation) is prepared.PreparedTransition, 'INVALID_STATE_PREPARATION')
        require(type(decision_document) is sources.GitDocument, 'INVALID_DECISION_SOURCE')
        require(type(exact_scope) is tuple and 0 < len(exact_scope) <= 1000
                and all(isinstance(item, str) for item in exact_scope), 'INVALID_DECISION_SCOPE')
        require(all(callable(value) for value in (read_reply, interpret, read_grant)),
                'HUMAN_SOURCE_UNAVAILABLE')
        self.preparation = preparation
        self.document = decision_document
        self.candidate_repository = candidate_repository
        self.source_key = source_key
        self.exact_scope = exact_scope
        self.read_reply, self.interpret, self.read_grant = read_reply, interpret, read_grant

    def __call__(self, request):
        feature = self.preparation.read(request)
        require(request.task_id.startswith('ACCEPT-'), 'ACCEPTANCE_TASK_REQUIRED')
        detail = tc.read_utf8(self.preparation.root / f'tasks/{request.task_id}.md')
        fields = tc.type_contract_fields(detail, request.task_id)
        retained = feature.type_contracts.get(request.task_id, {})
        require(all(fields.get(key) == retained.get(key)
                    for key in ('Target SHA', 'Acceptance scope', 'Acceptance brief')),
                'ACCEPTANCE_SCOPE_CHANGED')
        phase, needs_decision = guard.requirements(request.task_id, request.target, fields)
        require(phase is None and needs_decision, 'ACCEPTANCE_DECISION_TRANSITION_REQUIRED')
        brief = fields.get('Acceptance brief')
        declared = set(tc.declared_gist_names(detail))
        require(brief in declared and self.document.logical_path in declared,
                'ACCEPTANCE_SOURCE_NOT_DECLARED')
        root = self.preparation.root
        owners = [repo for repo in feature.repositories.values()
                  if repo['role'] == 'project-management' and root.is_relative_to(Path(repo['path']))]
        require(len(owners) == 1, 'INVALID_DECISION_SOURCE')
        management = owners[0]
        repository = Path(management['path']).resolve()
        require(Path(self.document.repository).resolve() == repository
                and self.document.expected_head == management['actual_head']
                and (repository / self.document.relative_path).resolve() == (root / self.document.logical_path).resolve(),
                'INVALID_DECISION_SOURCE')
        brief_document = sources.GitDocument(brief, repository,
            (root / brief).relative_to(repository).as_posix(), management['actual_head'])
        candidate = feature.repositories.get(self.candidate_repository)
        require(candidate is not None and candidate['role'] != 'project-management'
                and candidate['actual_head'] == fields.get('Target SHA'), 'ACCEPTANCE_TARGET_MISMATCH')

        def originals():
            snapshot = sources.read_git_documents((self.document, brief_document))
            require(sum(map(len, snapshot.documents.values())) <= MAX_BYTES, 'RESOURCE_LIMIT')
            raw = snapshot.object(self.document.logical_path, 'decision-evidence-v1')
            # For acceptance the Git target is the actual product candidate,
            # not the management commit that happens to retain its brief/reply.
            # The full current brief body is compared independently as well.
            current = dict(feature=root.name, decision_kind='acceptance',
                target_ref=dict(source_key=self.source_key, version_kind='git', version=candidate['actual_head']),
                exact_scope=list(self.exact_scope),
                body=snapshot.documents[brief].decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'))
            return snapshot, raw, current

        snapshot, record, current = originals()
        grant = deepcopy(self.read_grant(request, deepcopy(record)))
        require(type(grant) is human.HumanGrant, 'HUMAN_AUTHORITY_UNVERIFIED')

        def read_current():
            again, raw, material = originals()
            require(again == snapshot and raw == record and material == current, 'ACCEPTANCE_SOURCE_CHANGED')
            return material

        def revalidate(observed_request):
            require(observed_request == request, 'STATE_PREPARATION_MISMATCH')
            require(self.read_grant(request, deepcopy(record)) == grant, 'HUMAN_AUTHORITY_CHANGED')
            read_current()
            self.preparation.read(request)

        return guard.TransitionEvidence(request.digest,
            human_decision=guard.HumanDecisionInputs(record, read_current, self.read_reply, self.interpret, grant),
            revalidate=revalidate)
