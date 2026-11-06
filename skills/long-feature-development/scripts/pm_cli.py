"""Rootless Skill operations using the configured Project-Manage CLI only.

No service filesystem, HTTP implementation, authentication or retry is owned here.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def module(cli):
    source = Path(cli).resolve().with_name('task_workflow.py')
    spec = importlib.util.spec_from_file_location('pm_task_workflow', source)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    loaded.CLI = Path(cli).resolve()
    return loaded


def document_path(boundary, path, write=False):
    # Exact logical paths, never a local service path. Server validates canonical
    # layout, identities, YAML, dependency graph and generated indexes.
    prefix = 'feature/' + boundary['feature_key'] + '/'
    parts = path.split('/')
    if not path.startswith(prefix) or any(x in ('', '.', '..') for x in parts) or '\\' in path:
        raise ValueError('Document must be a canonical path in the assigned Feature')
    tail = path[len(prefix):]
    if tail not in ('STATUS.md', 'DESIGN.md', 'TASKS.md', 'VERBAL.md'):
        if len(parts) != 4 or parts[2] not in ('tasks', 'design') or not parts[3].endswith('.md'):
            raise ValueError('Unsupported canonical document')
    if write:
        targets = boundary.get('writable_documents', [])
        if not isinstance(targets, list) or any(not isinstance(item, str) for item in targets):
            raise ValueError('writable_documents must be an array of exact canonical paths')
        if path not in targets:
            raise ValueError('Document write not granted by caller boundary')
    return path


def raw_document(ack):
    if not isinstance(ack, dict) or not isinstance(ack.get('body'), dict) or not isinstance(ack['body'].get('raw'), str):
        raise ValueError('CLI response has no DocumentView.body.raw')
    return ack['body']['raw']


def run(args, workflow, boundary, calls):
    if args.operation in ('context', 'update', 'report-save'):
        return workflow.run(args, boundary, calls)
    if args.operation == 'service-context':
        command = ['integration', 'context']
        if args.project_key:
            command += ['--project-key', args.project_key]
        code, ack, err = workflow.invoke(boundary, command, calls)
        return code, {'cli_result': ack, 'cli_error': err}
    if args.operation == 'report-get':
        code, ack, err = workflow.read(boundary, calls)
        if code != 0:
            return code, {'cli_result': ack, 'cli_error': err}
        body = ack['body'].get('body')
        if not isinstance(body, str):
            raise ValueError('CLI response has no report body')
        Path(args.output).write_bytes(body.encode('utf-8'))
        return 0, {'saved': str(args.output), 'body_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest()}
    path = document_path(boundary, args.path, args.operation == 'document-put')
    command = ['integration', 'document-get', '--path', path]
    if args.operation == 'document-get':
        code, ack, err = workflow.invoke(boundary, command, calls)
        if code != 0:
            return code, {'cli_result': ack, 'cli_error': err}
        raw = raw_document(ack)
        Path(args.output).write_bytes(raw.encode('utf-8'))
        return 0, {'path': path, 'saved': str(args.output), 'raw_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest()}
    raw = Path(args.raw_file).read_bytes().decode('utf-8')
    code, ack, err = workflow.invoke(boundary, ['integration', 'document-update', '--path', path,
                                              '--raw-file', str(args.raw_file)], calls)
    receipt = {'write_cli_exit': code, 'cli_result': ack, 'cli_error': err,
               'readback': 'not_attempted', 'retried': False,
               'request_authorship_from_readback': 'NOT_PROVEN', 'durable_operation_lookup': 'UNAVAILABLE'}
    if code not in (0, 3):
        return code, {'receipt': receipt}
    rcode, current, rerr = workflow.invoke(boundary, command, calls)
    if rcode != 0:
        receipt.update(readback='UNKNOWN', readback_cli_exit=rcode, readback_error=rerr)
        return 2, {'receipt': receipt}
    matches = raw_document(current) == raw
    # Keep hook/error facts, but do not return a full old/new document archive.
    if isinstance(ack, dict) and isinstance(ack.get('body'), dict):
        receipt['cli_result'] = {k: v for k, v in ack['body'].items()
                                 if k in ('operation_status', 'hook_results', 'warnings')}
    receipt.update(readback='MATCH' if matches else 'MISMATCH',
                   submitted_raw_sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest())
    return (code if matches else 2), {'receipt': receipt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True, help='Actual current project_manage.py in its repository')
    parser.add_argument('--boundary', type=Path, required=True, help='Local own-author scope and CLI config locator')
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('context')
    commands.add_parser('service-context').add_argument('--project-key')
    commands.add_parser('update').add_argument('--data-file', type=Path, required=True)
    commands.add_parser('report-save').add_argument('--body-file', type=Path, required=True)
    commands.add_parser('report-get').add_argument('--output', type=Path, required=True)
    for operation in ('document-get', 'document-put'):
        command = commands.add_parser(operation)
        command.add_argument('--path', required=True)
        command.add_argument('--output' if operation == 'document-get' else '--raw-file', type=Path, required=True)
    args = parser.parse_args()
    calls = []
    try:
        workflow = module(args.cli)
        boundary = workflow.boundary(args.boundary)
        code, result = run(args, workflow, boundary, calls)
        result['caller_boundary'] = {k: boundary[k] for k in ('feature_key', 'task_id', 'writer', 'authority_reference')}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError) as error:
        code, result = 2, {'error': str(error), 'retried': False}
    result['measurements'] = {'cli_calls': calls, 'http_requests': 'UNKNOWN: instrument server',
                              'transport_bytes': 'UNKNOWN: stdout is not wire bytes',
                              'backend_io': 'UNKNOWN: instrument server'}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
