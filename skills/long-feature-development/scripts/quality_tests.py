#!/usr/bin/env python3
"""Test facts and content applicability, not permission or execution authority."""
from dataclasses import dataclass
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from context_loader import safe_relative
from review_source import _run, SHA

COUNTERS = ('Executed', 'Passed', 'Failed', 'Skipped', 'Unknown')


def audit_counts(contract, checks):
    """Do not equate checklist rows with execution units (one suite may run many).

    Contradictory originals do not prove which original is wrong. Require an
    execution-source investigation instead of silently choosing PASS or claiming
    a product failure. Only fixed codes/counts are returned, never source bodies.
    """
    counts = {}
    for name in COUNTERS:
        value = contract.get(name)
        if not isinstance(value, str) or re.fullmatch(r'[0-9]{1,9}', value) is None:
            return dict(status='UNRESOLVED', severity='P1', reason_codes=['INVALID_TEST_COUNTS'], counts={})
        counts[name] = int(value)
    reasons = set()
    outcomes = {check['outcome'] for check in checks}
    # Runners differ on whether skipped/unknown units count as executed. Do not
    # impose an undocumented equality; definite pass/fail units must have run,
    # and every executed unit must have some recorded disposition.
    if not counts['Passed'] + counts['Failed'] <= counts['Executed'] <= sum(counts[name] for name in COUNTERS[1:]):
        reasons.add('TEST_COUNT_TOTAL_MISMATCH')
    if (('FAIL' in outcomes) != bool(counts['Failed'])
            or 'PASS' in outcomes and counts['Passed'] == 0
            or outcomes & {'UNKNOWN', 'NOT-RUN'} and counts['Unknown'] == 0
            or counts['Executed'] == 0 and outcomes & {'PASS', 'FAIL'}):
        reasons.add('TEST_SUMMARY_DETAIL_CONFLICT')
    if counts['Failed']:
        reasons.add('TEST_TASK_RECORDED_FAILURE')
    if counts['Unknown']:
        reasons.add('TEST_TASK_UNRESOLVED_RESULTS')
    if counts['Skipped'] and outcomes == {'PASS'}:
        reasons.add('TEST_SUMMARY_DETAIL_CONFLICT')
    unresolved = bool(reasons & {'TEST_COUNT_TOTAL_MISMATCH', 'TEST_SUMMARY_DETAIL_CONFLICT'})
    return dict(status='UNRESOLVED' if unresolved else 'CONSISTENT',
                severity='P1' if reasons else None, reason_codes=sorted(reasons), counts=counts)


def task_binding(feature, tests):
    """Keep the original test target truthful; applicability is a separate fact."""
    task = tests['test_task']
    targets = tests['target_refs']
    if not isinstance(targets, dict) or not targets or any(
            not isinstance(sha, str) or SHA.fullmatch(sha) is None for sha in targets.values()):
        return 'INVALID_TEST_TARGET'
    refs = {row['repository']: row['head_sha'] for row in feature.details.get(task, ('', []))[1]}
    if not set(targets) <= set(feature.repositories) or not set(targets) <= set(refs):
        return 'TEST_TASK_REPOSITORY_MISMATCH'
    target = feature.type_contracts.get(task, {}).get('Target SHA')
    matched = [name for name, sha in targets.items() if sha == target]
    # The legacy singular Target SHA must identify one tested product repository,
    # not coincidentally match the management repository or two ambiguous rows.
    if len(matched) != 1 or feature.repositories[matched[0]].get('role') == 'project-management':
        return 'TEST_TASK_REPORT_TARGET_MISMATCH'
    # The primary task's working/completion HEAD may advance while recording
    # metadata; its Target SHA, not that bookkeeping HEAD, is the run target.
    # Additional repositories need their explicit retained snapshot binding.
    if any(refs[name] != sha for name, sha in targets.items() if name != matched[0]):
        return 'TEST_TASK_REPORT_TARGET_MISMATCH'
    return None


@dataclass(frozen=True)
class TestCoverage:
    """Fresh authenticated host attestation, NEVER a user-uploaded scope flag.

    For this exact test digest and repository, the host verified the complete
    semantic input/dependency closure and unchanged non-Git inputs. Paths include
    sources, test runner, configs/locks, dependency/discovery directories (also
    currently absent inputs). Dynamic/unbounded dependencies cannot be attested
    as a short list. runtime_basis identifies the host's retained verification;
    it is not authenticated just by constructing this dataclass.
    """
    test_digest: str
    repository_ref: str
    paths: tuple
    runtime_basis: str


def observe_impact(repo, original, candidate, *, coverage=None):
    """Read actual commit content, never infer semantic change from SHA alone.

    Without verified coverage, a tree difference is UNKNOWN, not proof that an
    added file is used. Complete identical trees are reusable; a verified input
    closure ignores unrelated additions but catches dependencies/config changes.
    Exact operation refs/leases remain the responsibility of the delivery reader.
    """
    if not all(isinstance(sha, str) and SHA.fullmatch(sha) for sha in (original, candidate)):
        raise ValueError('INVALID_TEST_TARGET')
    root = Path(repo).resolve(strict=True)
    actual = Path(_run(root, 'rev-parse', '--show-toplevel')[1].decode('utf-8').strip()).resolve(strict=True)
    if actual != root:
        raise ValueError('REPO_IDENTITY_MISMATCH')
    grafts = Path(_run(root, 'rev-parse', '--git-path', 'info/grafts')[1].decode('utf-8').strip())
    if not grafts.is_absolute():
        grafts = root / grafts
    if grafts.exists() or grafts.is_symlink():
        raise ValueError('GRAFTED_HISTORY_UNSUPPORTED')
    trees = []
    for sha in (original, candidate):
        if _run(root, 'cat-file', '-t', sha)[1].strip() != b'commit':
            raise ValueError('COMMIT_REQUIRED')
        trees.append(_run(root, 'rev-parse', sha + '^{tree}')[1].strip())
    if trees[0] == trees[1]:
        return 'UNCHANGED_TREE'
    if coverage is None:
        return 'UNVERIFIED_TEST_IMPACT'
    if (type(coverage) is not TestCoverage or type(coverage.paths) is not tuple
            or not 0 < len(coverage.paths) <= 1000 or len(set(coverage.paths)) != len(coverage.paths)
            or not isinstance(coverage.runtime_basis, str) or not coverage.runtime_basis.strip()):
        raise ValueError('INVALID_TEST_COVERAGE')
    for path in coverage.paths:
        safe_relative(path)
        if any(part.casefold() == '.git' for part in path.split('/')) or '\\' in path:
            raise ValueError('INVALID_TEST_COVERAGE')
    changed = _run(root, 'diff', '--quiet', '--no-ext-diff', '--no-textconv',
                   '--ignore-submodules=none', original, candidate, '--', *coverage.paths,
                   accepted=(0, 1))[0]
    return 'TEST_INPUTS_CHANGED' if changed else 'UNCHANGED_VERIFIED_INPUTS'
