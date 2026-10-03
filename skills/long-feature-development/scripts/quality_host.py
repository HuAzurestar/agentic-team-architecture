#!/usr/bin/env python3
"""Read actual quality originals and Git facts before invoking the pure policy.

Provenance is an authenticated host responsibility, never imported from files.
No dynamic plugins, JSON authority flags, task writes or merge operations.
"""
from dataclasses import dataclass, field
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode = True
from context_loader import LocalMarkdownLoader, load_feature
import task_context as tc
import quality_source as sources
import quality_git as git
import quality_policy as policy
import review_report as reports
from review_resume import _object

MAX_CONFIG_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class SourceRoles:
    request: str
    report: str
    tests: str
    checklist: str
    related_reports: tuple = ()
    result_tests: str | None = None


@dataclass(frozen=True)
class ProvenanceRead:
    # Immutable complete inputs for the configured identity/authority reader.
    digest: str
    request: bytes
    sources: tuple
    versions: tuple
    feature_digest: str


@dataclass(frozen=True)
class HostProvenance:
    """Actual independently verified host facts bound to ProvenanceRead.digest.

    Constructing this type is not authentication. read_provenance must verify
    reviewer identity/context, closures, exact exclusions/reuse and human reply
    provenance using the host's real transport and retained authorization.
    """
    digest: str
    independent_reports: frozenset = field(default_factory=frozenset)
    excluded_scopes: frozenset = field(default_factory=frozenset)
    reused_checks: frozenset = field(default_factory=frozenset)
    acceptance_bindings: frozenset = field(default_factory=frozenset)
    current_review_digest: str = ''
    report_evidence: object = None
    decision_sources: object = None


@dataclass(frozen=True)
class Assessment:
    result: dict
    feature: object = None
    request: object = None
    observations: object = None
    report_evidence: object = None
    decision_sources: object = None

    def for_task(self, source_ref, task_id):
        """Pass freshly observed inputs to the existing selector/state guard.

        The caller supplies its current selection/transition binding. Those
        consumers independently compare the actual plan and recompute policy.
        Never cache this return value across an operation boundary.
        """
        from task_next import QualityInputs
        require(self.observations is not None, 'QUALITY_HOST_READ_FAILED')
        require(task_id in self.feature.records, 'UNKNOWN_TASK')
        return QualityInputs(source_ref, task_id, self.feature, deepcopy(self.request),
                             self.observations, self.report_evidence, self.decision_sources)


class HostError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise HostError(code)


def _feature(root, overrides):
    return tc.validate_feature(load_feature(LocalMarkdownLoader(root)), tc.LocalGitProbe(root, overrides))


def _originals(feature, snapshot, roles):
    request = snapshot.object(roles.request, 'quality-request-v1')
    require(set(request) == policy.FIELDS, 'INVALID_QUALITY_REQUEST')
    report = snapshot.require_object(roles.report, 'report-v1', request['report'])
    require(type(roles.related_reports) is tuple and len(roles.related_reports) == len(request['related_reports']),
            'REPORT_SOURCE_MISMATCH')
    related = [snapshot.require_object(path, 'report-v1', expected)
               for path, expected in zip(roles.related_reports, request['related_reports'])]
    tests = snapshot.require_object(roles.tests, 'test-results-v1', request['tests'])
    results = []
    require((roles.result_tests is None) == (request['result_tests'] is None), 'TEST_SOURCE_MISMATCH')
    if roles.result_tests is not None:
        results.append((roles.result_tests, snapshot.require_object(roles.result_tests, 'test-results-v1',
                                                                    request['result_tests'])))
    checklist = snapshot.object(roles.checklist, 'quality-checklist-v1')
    require(set(checklist) == {'schema', 'required_checks'} and
            policy.canonical(checklist['required_checks']) == policy.canonical(request['required_checks']),
            'CHECKLIST_SOURCE_MISMATCH')
    require(request['checklist_ref']['path'] == roles.checklist and
            (roles.checklist, request['checklist_ref']['sha256']) in snapshot.source_refs,
            'CHECKLIST_SOURCE_MISMATCH')
    # A real original is still the wrong original if a different task declared it.
    for path, obj, key in [(roles.report, report, 'review_task'),
                           *[(p, obj, 'review_task') for p, obj in zip(roles.related_reports, related)],
                           (roles.tests, tests, 'test_task'), *[(p, obj, 'test_task') for p, obj in results]]:
        task = obj[key]
        require(feature.type_contracts.get(task, {}).get('Result gist') == path, 'TASK_SOURCE_MISMATCH')
        record = feature.documents.records.get(path)
        require(record is not None and (path, record.content_digest) in snapshot.source_refs,
                'TASK_SOURCE_MISMATCH')
    return request


def _delivery(feature, bindings, request):
    require(type(bindings) is tuple and 0 < len(bindings) <= 1000, 'INVALID_REPOSITORY_BINDING')
    observed = {}
    for binding in bindings:
        require(type(binding) is git.IntegrationBinding and binding.repository_ref not in observed,
                'INVALID_REPOSITORY_BINDING')
        registered = feature.repositories.get(binding.repository_ref)
        require(registered is not None and Path(registered['path']).resolve() == Path(binding.repo).resolve(),
                'REPO_IDENTITY_MISMATCH')
        frozen = request['frozen'].get(binding.repository_ref)
        require(isinstance(frozen, dict), 'INCOMPLETE_REPOSITORY_SCOPE')
        result = git.observe_delivery(binding, request['phase'], result_sha=frozen.get('result'))
        require(result['valid'], 'DELIVERY_NOT_READY')
        observed[binding.repository_ref] = result['facts']
    return observed


def evaluate(root, *, documents, roles, repositories, read_provenance=None, repo_overrides=None):
    """Strict local feature + committed originals + live Git + real host reader.

    documents/roles/repositories are independently selected host configuration.
    The reader receives immutable originals and must return fresh provenance
    twice. Missing provenance produces an ordinary policy denial, not fake PASS.
    This read-only entry does not accept prepared/dirty task metadata; writers
    need a separate explicitly reconciled transition adapter, never a dirty flag.
    """
    try:
        require(type(roles) is SourceRoles, 'INVALID_SOURCE_ROLES')
        root = Path(root).resolve(strict=True)
        feature = _feature(root, repo_overrides)
        feature_digest = policy.feature_digest(feature)
        registered = {Path(r['path']).resolve(): r['actual_head'] for r in feature.repositories.values()}
        require(type(documents) is tuple and all(type(d) is sources.GitDocument and
                registered.get(Path(d.repository).resolve()) == d.expected_head for d in documents),
                'UNREGISTERED_SOURCE')
        require(all(d.logical_path not in feature.documents.records or
                    (Path(d.repository) / d.relative_path).resolve() == (root / d.logical_path).resolve()
                    for d in documents), 'TASK_SOURCE_MISMATCH')
        snapshot = sources.read_git_documents(documents)
        request = _originals(feature, snapshot, roles)
        delivery = _delivery(feature, repositories, request)
        digest = policy.request_digest(dict(feature=feature_digest, request=request,
            versions=dict(snapshot.versions), sources=sorted(snapshot.source_refs), delivery=delivery))
        probe = ProvenanceRead(digest, policy.canonical(request), tuple(sorted(snapshot.documents.items())),
                               tuple(sorted(snapshot.versions.items())), feature_digest)

        def provenance():
            if read_provenance is None:
                return HostProvenance(digest)
            require(callable(read_provenance), 'INVALID_PROVENANCE_READER')
            try:
                result = deepcopy(read_provenance(probe))
            except Exception:
                raise HostError('PROVENANCE_UNAVAILABLE') from None
            require(type(result) is HostProvenance and result.digest == digest, 'PROVENANCE_BINDING_MISMATCH')
            for name in ('independent_reports', 'excluded_scopes', 'reused_checks', 'acceptance_bindings'):
                require(type(getattr(result, name)) is frozenset, 'INVALID_PROVENANCE')
            require(result.report_evidence is None or type(result.report_evidence) is reports.VerifiedReportEvidence,
                    'INVALID_PROVENANCE')
            return result

        proof = provenance()
        observed = policy.QualityObservations(policy.request_digest(request), feature_digest,
            source_refs=snapshot.source_refs, independent_reports=proof.independent_reports,
            excluded_scopes=proof.excluded_scopes, reused_checks=proof.reused_checks,
            integration=delivery, remote_targets=frozenset((name, facts['remote_target']) for name, facts in delivery.items()),
            acceptance_bindings=proof.acceptance_bindings, required_repositories=frozenset(delivery),
            checklist_binding=policy.request_digest(dict(ref=request['checklist_ref'], required_checks=request['required_checks'])),
            current_review_digest=proof.current_review_digest)
        result = policy.assess_quality(feature, request, observed=observed,
                                       report_evidence=proof.report_evidence, decision_sources=proof.decision_sources)
        # Recheck complete originals, feature graph, actual refs and authority;
        # not just the selected report or an independently moving HEAD alias.
        require(provenance() == proof, 'QUALITY_PROVENANCE_CHANGED')
        again = sources.read_git_documents(documents)
        require(again == snapshot, 'QUALITY_SOURCE_CHANGED')
        require(policy.feature_digest(_feature(root, repo_overrides)) == feature_digest, 'QUALITY_FEATURE_CHANGED')
        require(_delivery(feature, repositories, request) == delivery, 'QUALITY_DELIVERY_CHANGED')
        return Assessment(result, feature, request, observed, proof.report_evidence, proof.decision_sources)
    except Exception as error:
        # Never echo parser bodies, repository URLs, credentials or callback text.
        code = str(error) if type(error) is HostError else 'QUALITY_HOST_READ_FAILED'
        if type(error) is tc.ContextError and str(error) in {'HIDDEN_INDEX_STATE', 'INDEX_STATE_UNAVAILABLE'}:
            code = str(error)
        return Assessment(dict(allowed=False, eligible=False, reason_codes=[code],
            missing_checks=[], open_blockers=[], stale_refs=[], evidence_refs=[],
            required_next_actions=['repair-quality-source-or-host-provenance'],
            effect='NOT_APPLIED', merge_authorized=False))


def configured_inputs(root, raw, repo_overrides=None):
    """Resolve an explicitly selected configuration, never authority or code.

    Repository locations and HEADs come from the strict reader, not JSON paths
    or expected-head assertions. Authenticated provenance remains a Python host
    dependency and cannot be selected/imported from the configuration.
    """
    require(isinstance(raw, bytes) and len(raw) <= MAX_CONFIG_BYTES, 'INVALID_QUALITY_CONFIG')
    try:
        config = _object(raw.decode('utf-8-sig'), 'quality-host-config-v1')
        require(set(config) == {'schema', 'roles', 'documents', 'repositories'}, 'INVALID_QUALITY_CONFIG')
        role = config['roles']
        require(isinstance(role, dict) and set(role) == {'request', 'report', 'tests', 'checklist',
                                                       'related_reports', 'result_tests'}, 'INVALID_QUALITY_CONFIG')
        require(isinstance(role['related_reports'], list) and len(role['related_reports']) <= 1000,
                'INVALID_QUALITY_CONFIG')
        roles = SourceRoles(**(role | {'related_reports': tuple(role['related_reports'])}))
        for key in ('documents', 'repositories'):
            require(isinstance(config[key], list) and 0 < len(config[key]) <= 1000, 'INVALID_QUALITY_CONFIG')
        feature = _feature(Path(root).resolve(strict=True), repo_overrides)
        documents, repositories = [], []
        for item in config['documents']:
            require(isinstance(item, dict) and set(item) == {'logical_path', 'repository', 'relative_path'},
                    'INVALID_QUALITY_CONFIG')
            registered = feature.repositories[item['repository']]
            documents.append(sources.GitDocument(item['logical_path'], Path(registered['path']),
                                                 item['relative_path'], registered['actual_head']))
        keys = {'repository_ref', 'remote', 'expected_remote', 'source_branch', 'source_sha',
                'source_tree', 'target_branch', 'target_before'}
        for item in config['repositories']:
            require(isinstance(item, dict) and set(item) == keys, 'INVALID_QUALITY_CONFIG')
            registered = feature.repositories[item['repository_ref']]
            repositories.append(git.IntegrationBinding(repo=Path(registered['path']), **item))
        return dict(documents=tuple(documents), roles=roles, repositories=tuple(repositories),
                    repo_overrides=repo_overrides)
    except HostError:
        raise
    except Exception:
        raise HostError('INVALID_QUALITY_CONFIG') from None


def render_result(result):
    """Human-readable diagnosis, with no source bodies or implied operation grant."""
    lines = ['Quality: ' + ('eligible' if result['allowed'] else 'blocked'),
             'Effect: NOT_APPLIED; merge authority: not granted']
    for label, key in [('Reasons', 'reason_codes'), ('Missing checks', 'missing_checks'),
                       ('Open blockers', 'open_blockers'), ('Stale refs', 'stale_refs'),
                       ('Evidence refs', 'evidence_refs'), ('Next checks', 'required_next_actions')]:
        values = result.get(key, [])
        if values:
            lines.extend(['', label + ':'])
            lines.extend('- ' + (value if isinstance(value, str) else json.dumps(value, ensure_ascii=True))
                         for value in values)
    return '\n'.join(lines)


def main(argv=None, *, read_provenance=None):
    """CLI diagnostics, optionally embedded by an authenticated Python host.

    Standalone CLI has no authenticated reviewer/human transport: missing facts
    remain denied. No command-line switch or JSON property manufactures them.
    A real host may inject its already-configured reader through the Python API.
    """
    parser = argparse.ArgumentParser(description='Read actual quality evidence without applying any operation.')
    parser.add_argument('feature_directory')
    parser.add_argument('--config', required=True, help='Explicit quality-host-config-v1 source bindings; not authority')
    parser.add_argument('--repo', action='append', default=[], metavar='NAME=PATH')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    args = parser.parse_args(argv)
    started, phase, targets = time.monotonic(), None, {}
    exit_code = 2
    try:
        path = Path(args.config)
        # Bounded explicit-file read, including link/path checks; never import code.
        loader = LocalMarkdownLoader(path.parent.resolve())
        raw, identity = loader._read_raw(path.name, MAX_CONFIG_BYTES)
        inputs = configured_inputs(Path(args.feature_directory), raw, tc.parse_repo_overrides(args.repo))
        assessment = evaluate(Path(args.feature_directory), **inputs, read_provenance=read_provenance)
        require(loader._read_raw(path.name, len(raw)) == (raw, identity), 'QUALITY_CONFIG_CHANGED')
        result = assessment.result
        if assessment.request is not None:
            phase = assessment.request.get('phase')
            targets = assessment.request.get('target_refs', {})
        exit_code = 0 if result['allowed'] else (1 if assessment.observations is not None else 2)
    except Exception:
        result = dict(allowed=False, eligible=False, reason_codes=['INVALID_QUALITY_CONFIG'],
            missing_checks=[], open_blockers=[], stale_refs=[], evidence_refs=[],
            required_next_actions=['check-explicit-source-bindings-and-feature-context'],
            effect='NOT_APPLIED', merge_authorized=False)
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')) if args.format == 'json' else render_result(result))
    print(json.dumps(dict(event='quality.evaluate', phase=phase, allowed=result['allowed'],
        reason_codes=result['reason_codes'], target_refs=targets,
        elapsed_ms=round((time.monotonic() - started) * 1000, 3)), separators=(',', ':')), file=sys.stderr)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
