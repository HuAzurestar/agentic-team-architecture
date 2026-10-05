#!/usr/bin/env python3
"""Actual-source preflight for applying comments; no merge or publication."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from decision_evidence import POINT, changed_span, line
from decision_source import read_git_current, SourceError, _point
from review_source import read_git_reviews, _run, _head, SHA, ReviewSourceError
from review_comments import MAX_REVIEWS, MAX_BYTES, ReviewCommentError


@dataclass(frozen=True)
class GitSampleBinding:
    """Registered target source, supplied by the host independently of comments."""
    repo: Path
    relative_path: str
    expected_head: str
    target_ref: str
    feature: str


def _sample(body, basis, selector):
    if selector:
        return _point(body, selector)
    if 'line_start' in basis:
        lines = body.splitlines(keepends=True)
        if basis['line_end'] > len(lines):
            raise ReviewSourceError('SAMPLE_RANGE_CHANGED')
        return ''.join(lines[basis['line_start'] - 1:basis['line_end']])
    return body


def _historical(configured, basis, selector):
    version = basis.get('git_basis')
    if not isinstance(version, str) or not SHA.fullmatch(version):
        raise ReviewSourceError('BASIS_VERSION_UNVERIFIED')
    entry = _run(configured.repo, 'ls-tree', '-z', version, '--', configured.relative_path)[1]
    rows = entry.rstrip(b'\0').split(b'\0')
    if len(rows) != 1 or b'\t' not in rows[0]:
        raise ReviewSourceError('BASIS_SOURCE_UNAVAILABLE')
    header, name = rows[0].split(b'\t', 1)
    fields = header.split()
    if (len(fields) != 3 or fields[0] not in (b'100644', b'100755') or fields[1] != b'blob'
            or name.decode('utf-8') != configured.relative_path):
        raise ReviewSourceError('BASIS_SOURCE_UNAVAILABLE')
    blob = fields[2].decode('ascii')
    if int(_run(configured.repo, 'cat-file', '-s', blob)[1]) > MAX_BYTES:
        raise ReviewSourceError('RESOURCE_LIMIT')
    text = _run(configured.repo, 'cat-file', 'blob', blob)[1].decode('utf-8').replace('\r\n', '\n')
    return _sample(text, basis, selector)


def _status(root):
    # A checkout's normal text/filter configuration determines its clean state.
    # Disabling global autocrlf can falsely mark a clean Windows checkout dirty.
    configured_root = Path(_run(root, 'rev-parse', '--show-toplevel', configured=True)[1].decode('utf-8').strip()).resolve()
    if configured_root != root:
        raise ReviewSourceError('INVALID_REVIEW_BINDING')
    return _run(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all', configured=True)[1]


def assess_application(binding, observation, *, expected_working_head, expected_branch,
                       samples, authorized=False, authority_source_ref=''):
    """Check actual refs and samples before a separately journaled mutation.

    Missing master ancestry yields an exact sync requirement, never an implicit
    merge. Passing proves this observation only, not independent quality or human
    acceptance. The F03 writer must persist it, revalidate and conditionally act.
    """
    result = dict(preflight_passed=False, effect='NOT_APPLIED', merge_authorized=False,
                  reason_codes=[], sample_checks=[], required_actions=[], trace=None)
    try:
        if authorized is not True or not line(authority_source_ref):
            raise ReviewSourceError('AUTHORITY_REQUIRED')
        if (not isinstance(expected_working_head, str) or not SHA.fullmatch(expected_working_head)
                or not line(expected_branch) or not isinstance(samples, dict) or len(samples) > MAX_REVIEWS):
            raise ReviewSourceError('INVALID_REVIEW_APPLICATION')
        root = Path(binding['repo']).resolve(strict=True)
        branch = _run(root, 'symbolic-ref', '--quiet', '--short', 'HEAD')[1].decode('utf-8').strip()
        if branch != expected_branch or _head(root) != expected_working_head:
            raise ReviewSourceError('WORKING_REF_CHANGED')
        if _status(root):
            raise ReviewSourceError('DIRTY_WORKTREE')
        fresh = read_git_reviews(**binding, statuses=['PENDING', 'ADDRESSED', 'VERIFIED'])
        if (fresh['source_version'] != observation['source_version']
                or fresh['source_digest'] != observation['source_digest']
                or fresh['reviews_ref'] != observation['reviews_ref']
                or fresh['repository_ref'] != observation['repository_ref']):
            raise ReviewSourceError('REVIEW_SOURCE_CHANGED')
        selected = observation['records']
        if not isinstance(selected, list) or len(selected) > MAX_REVIEWS:
            raise ReviewSourceError('RESOURCE_LIMIT')
        actual = {record['rv_id']: record for record in fresh['records']}
        seen = set()
        for record in selected:
            identifier = record['rv_id']
            if identifier in seen or actual.get(identifier) != record:
                raise ReviewSourceError('REVIEW_CONTENT_CHANGED')
            seen.add(identifier)
        result['trace'] = dict(repository_ref=fresh['repository_ref'], working_branch=branch,
            working_head=expected_working_head, reviews_ref=fresh['reviews_ref'],
            master_sha=fresh['source_version']['value'], source_digest=fresh['source_digest'],
            rv_ids=[record['rv_id'] for record in selected], authority_source_ref=authority_source_ref)
        if not fresh['master_contained']:
            result['reason_codes'].append('MASTER_SYNC_REQUIRED')
            result['required_actions'].append(dict(kind='authorized-exact-master-sync',
                                                   sha=fresh['source_version']['value']))
            return result
        target_reads, target_bytes = {}, 0
        for record in selected:
            basis, target = record['Basis'], record['Target']
            configured = samples.get(basis['source_key'])
            if record.get('_legacy') or type(configured) is not GitSampleBinding:
                raise ReviewSourceError('SAMPLE_SOURCE_UNVERIFIED')
            if configured.target_ref != target['ref'] or configured.feature != target['feature']:
                raise ReviewSourceError('SAMPLE_TARGET_MISMATCH')
            selector = target.get('selector')
            if selector is not None and not POINT.fullmatch(selector):
                raise ReviewSourceError('SAMPLE_SELECTOR_UNSUPPORTED')
            if selector is not None and 'line_start' in basis:
                raise ReviewSourceError('AMBIGUOUS_SAMPLE_SELECTOR')
            read_args = dict(source_key=basis['source_key'], feature=target['feature'],
                decision_kind='point' if selector else 'acceptance',
                exact_scope=[selector] if selector else ['sample'], expected_head=configured.expected_head)
            key = (str(configured.repo), configured.relative_path, configured.expected_head, basis['source_key'], selector)
            if key not in target_reads:
                material = read_git_current(configured.repo, configured.relative_path, **read_args)
                target_bytes += len(material['body'].encode('utf-8'))
                if target_bytes > MAX_BYTES:
                    raise ReviewSourceError('RESOURCE_LIMIT')
                target_reads[key] = (configured, read_args, material)
            material = target_reads[key][2]
            body = material['body'] if selector else _sample(material['body'], basis, None)
            if _historical(configured, basis, selector) != basis['source_text']:
                raise ReviewSourceError('BASIS_PROVENANCE_MISMATCH')
            same = body == basis['source_text']
            result['sample_checks'].append(dict(rv_id=record['rv_id'], source_key=basis['source_key'],
                current_version=material['target_ref']['version'], basis_version=basis.get('git_basis'),
                status='UNCHANGED' if same else 'NEEDS_RECHECK',
                diff=None if same else changed_span(basis['source_text'], body)))
            if not same:
                result['reason_codes'].append('BASIS_NEEDS_RECHECK')
        # Re-observe remote and working state after target reads, not just before.
        again = read_git_reviews(**binding, statuses=['PENDING', 'ADDRESSED', 'VERIFIED'])
        if (again['source_version'] != fresh['source_version']
                or _head(root) != expected_working_head
                or _status(root)):
            raise ReviewSourceError('REVIEW_SOURCE_CHANGED')
        for configured, read_args, previous in target_reads.values():
            if read_git_current(configured.repo, configured.relative_path, **read_args) != previous:
                raise ReviewSourceError('SAMPLE_SOURCE_CHANGED')
        result['reason_codes'] = list(dict.fromkeys(result['reason_codes']))
        result['preflight_passed'] = not result['reason_codes']
    except (ReviewSourceError, ReviewCommentError, SourceError) as exc:
        result['reason_codes'] = [str(exc)]
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        result['reason_codes'] = ['INVALID_REVIEW_APPLICATION']
    finally:
        result['event'] = dict(name='reviews.preflight', passed=result['preflight_passed'],
                               reason_codes=list(result['reason_codes']))
    return result
