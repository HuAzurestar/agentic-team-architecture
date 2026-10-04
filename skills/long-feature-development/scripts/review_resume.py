#!/usr/bin/env python3
"""Read-only review reference/version recovery, not a report quality assessor."""
from __future__ import annotations
import json
from pathlib import Path
import re
from context_loader import LoaderError, safe_relative


def fail(code):
    # Diagnostics deliberately contain no report prose or provider credentials.
    raise LoaderError(code, 'review recovery rejected: ' + code)


def _markdown(text):
    """Scan fences before their bodies; comments and nested examples are inert."""
    fence, tag, body, comment = None, None, [], False
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if (match and match[1][0] == fence[0] and len(match[1]) >= len(fence)
                    and not line[match.end():].strip()):
                yield 'block', tag, '\n'.join(body)
                fence = None
                body = []
            else:
                body.append(line)
            continue
        if comment:
            if '-->' in line:
                comment = False
            continue
        if '<!--' in line:
            comment = '-->' not in line.split('<!--', 1)[1]
            continue
        if match:
            fence = match[1]
            tag = line[match.end():].strip()
            continue
        yield 'line', None, line


def declaration(detail):
    """Only a top-level task field opts in; examples/quotes are not control data."""
    values = []
    for kind, _, line in _markdown(detail):
        if kind != 'line':
            continue
        if line.startswith('- Review recovery:'):
            values.append(line.partition(':')[2].strip())
    if not values:
        return None
    if len(values) != 1 or not values[0]:
        fail('INVALID_REVIEW_REFERENCE')
    safe_relative(values[0])
    return values[0]


def _object(text, schema):
    # A whole JSON document or one explicitly tagged fence, never an arbitrary
    # example JSON block hidden inside report prose.
    stripped = text.strip()
    if not stripped.startswith('{'):
        blocks = [body for kind, tag, body in _markdown(text)
                  if kind == 'block' and tag == schema]
        if len(blocks) != 1:
            fail('INVALID_REVIEW_REFERENCE')
        stripped = blocks[0]

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail('INVALID_REVIEW_REFERENCE')
            result[key] = value
        return result

    try:
        obj = json.loads(stripped, object_pairs_hook=unique,
                         parse_constant=lambda _: fail('INVALID_REVIEW_REFERENCE'))
    except (ValueError, RecursionError):
        fail('INVALID_REVIEW_REFERENCE')
    if not isinstance(obj, dict) or obj.get('schema') != schema:
        fail('INVALID_REVIEW_REFERENCE')
    return obj


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        fail('INVALID_REVIEW_REFERENCE')
    return value


def recover(documents, detail, tasks, repositories, commit_exists, declaring_task=None):
    """Consume the complete loaded read set plus host-verified repository facts.

    All evidence must also be declared in this task's Gists. No file reads,
    network calls, report writes, status changes or reviewer dispatch occur here.
    commit_exists is provided by the host's real local Git probe.
    """
    import task_context as tc
    path = declaration(detail)
    if path is None:
        return None
    allowed = set(tc.declared_gist_names(detail))
    if len(allowed) > 1000 or sum(documents.records[p].byte_count for p in allowed
                                if p in documents.records) > 64 * 1024 * 1024:
        fail('RESOURCE_LIMIT')

    def source(ref, schema=None):
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
            fail('INVALID_REVIEW_REFERENCE')
        name, digest = ref['path'], ref['sha256']
        safe_relative(name)
        if name not in allowed or name not in documents.records:
            fail('EVIDENCE_MISSING')
        record = documents.records[name]
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            fail('INVALID_REVIEW_REFERENCE')
        if record.content_digest != digest:
            fail('STALE_REVIEW')
        return _object(record.legacy_text, schema) if schema else record

    if path not in allowed or path not in documents.records:
        fail('EVIDENCE_MISSING')
    request = _object(documents.read(path), 'review-resume-v1')
    feature = request.get('feature')
    task_id = _id(request.get('review_task'))
    attempt = _id(request.get('attempt_id'))
    if feature != documents.root.name or task_id not in tasks:
        fail('STALE_REVIEW')
    if tasks[task_id]['type'] != 'Review' and not task_id.startswith('REVIEW-'):
        fail('INVALID_REVIEW_REFERENCE')
    owner = tasks.get(declaring_task)
    review_done = tasks[task_id]['state'] == 'DONE'
    owner_done = owner is not None and owner['state'] == 'DONE'
    # History is derived from validated task facts, never a flag in the report.
    # An in-progress review must still bind the actual candidate. A rework
    # dependent on a completed report can retain its source after its own fix.
    history_allowed = review_done and (owner_done or (
        owner is not None and owner['type'] == 'Rework'
        and task_id in owner['dependencies']))
    targets = request.get('target_refs')
    if not isinstance(targets, dict) or not targets:
        fail('INVALID_REVIEW_REFERENCE')
    current_targets = {}
    changed_target = False
    for name, sha in targets.items():
        if name not in repositories or not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{40}', sha):
            fail('INVALID_REVIEW_REFERENCE')
        repo = repositories[name]
        if not commit_exists(Path(repo['path']), sha):
            fail('EVIDENCE_MISSING')
        current_targets[name] = repo['actual_head']
        if sha != repo['actual_head']:
            if not history_allowed:
                fail('STALE_REVIEW')
            changed_target = True
    packet = source(request.get('packet_ref'), 'review-packet-v1')
    report = source(request.get('report_ref'), 'report-v1')
    checklist = request.get('checklist_ref')
    source(checklist)
    for obj in (packet, report):
        if (obj.get('feature') != feature or obj.get('review_task') != task_id
                or obj.get('attempt_id') != attempt or obj.get('target_refs') != targets
                or obj.get('checklist_ref') != checklist):
            fail('STALE_REVIEW')
    if _id(packet.get('packet_id')) != report.get('packet_id'):
        fail('STALE_REVIEW')
    evidence = report.get('evidence_refs')
    if not isinstance(evidence, list) or not evidence:
        fail('EVIDENCE_MISSING')
    if len(evidence) > 1000:
        fail('RESOURCE_LIMIT')
    for ref in evidence:
        source(ref)
    findings = report.get('findings')
    if not isinstance(findings, list):
        fail('INVALID_REVIEW_REFERENCE')
    if len(findings) > 10000:
        fail('RESOURCE_LIMIT')
    seen, opened = {}, []
    for finding in findings:
        if not isinstance(finding, dict):
            fail('INVALID_REVIEW_REFERENCE')
        key = _id(finding.get('id'))
        if finding.get('status') not in ('open', 'addressed', 'closed'):
            fail('INVALID_REVIEW_REFERENCE')
        if key in seen:
            if seen[key] != finding:
                fail('INVALID_REVIEW_REFERENCE')
            continue
        seen[key] = finding
        # Addressed is not independently closed. No severity/duplicate policy
        # is inferred here; report assessment and closure authority belong to F04.
        if finding['status'] != 'closed':
            opened.append(key)
    summary = report.get('summary')
    if not isinstance(summary, dict):
        fail('INVALID_REVIEW_REFERENCE')
    for obj in (summary, request):
        if 'open_finding_ids' in obj:
            ids = obj['open_finding_ids']
            if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids)
                    or len(ids) != len(set(ids)) or set(ids) != set(opened)):
                fail('REVIEW_SUMMARY_MISMATCH')
    historical = changed_target or (review_done and owner_done)
    next_action = ('needs-recheck' if changed_target else 'historical-reference') if historical else (
        'resume-rework' if opened else 'needs-independent-recheck')
    diagnostics = [{'code': 'STALE_REVIEW', 'reason': 'HISTORICAL_TARGET'}] if changed_target else []
    return {'review_task': task_id, 'attempt_id': attempt, 'target_refs': targets,
            'current_target_refs': current_targets,
            'evidence_scope': 'historical' if historical else 'current-candidate',
            'checklist_ref': checklist, 'report_ref': request['report_ref'],
            'open_finding_ids': opened,
            'open_findings': [{'feature': feature, 'report_ref': request['report_ref'],
                               'attempt_id': attempt, 'finding_id': key} for key in opened],
            'next_review_action': next_action,
            'diagnostics': diagnostics, 'quality_assessed': False}
