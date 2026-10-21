#!/usr/bin/env python3
"""Explicit runtime-owned profile persistence; no runtime discovery or tool execution."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import yaml

sys.dont_write_bytecode = True

class StateError(ValueError):
    pass

class Loader(yaml.SafeLoader):
    pass

Loader.yaml_implicit_resolvers = {
    k: [(tag, pattern) for tag, pattern in values if tag != 'tag:yaml.org,2002:timestamp']
    for k, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise StateError('YAML keys must be unique strings')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result

Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
KINDS = ('project-management', 'notification')
KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')

def same_json(left, right):
    """Compare JSON values without Python's bool/int coercion."""
    return json.dumps(left, sort_keys=True, ensure_ascii=False, allow_nan=False) == json.dumps(right, sort_keys=True, ensure_ascii=False, allow_nan=False)


def required_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise StateError(name + ' must be a nonempty string')
    return value

def absolute(value, name):
    path = Path(required_text(value, name))
    if not path.is_absolute():
        raise StateError(name + ' must be an explicit absolute path')
    return path

def read_yaml(path):
    try:
        value = yaml.load(Path(path).read_text(encoding='utf-8'), Loader=Loader)
        json.dumps(value, allow_nan=False)
        return value
    except (OSError, yaml.YAMLError, TypeError, ValueError) as exc:
        raise StateError('cannot read JSON-compatible YAML: ' + str(exc)) from exc

def validate(profile, kind, runtime_id):
    if kind not in KINDS or not isinstance(profile, dict):
        raise StateError('unknown profile kind or invalid mapping')
    required_text(runtime_id, 'runtime identity')
    if profile.get('runtime identity') != runtime_id:
        raise StateError('runtime identity mismatch')
    for name in ('profile', 'revision'):
        if not KEY.fullmatch(required_text(profile.get(name), name)):
            raise StateError(name + ' must be a safe identifier')
    if kind == 'project-management':
        roots = profile.get('management roots')
        if not isinstance(roots, dict) or not roots:
            raise StateError('management roots must be a nonempty mapping')
        for name, path in roots.items():
            required_text(name, 'root name')
            absolute(path, 'management root')
        if profile.get('selected root') not in roots:
            raise StateError('selected root must name a supplied mapping')
        absolute(profile.get('project registry'), 'project registry')
        for name in ('state writer reference', 'commit policy reference'):
            required_text(profile.get(name), name)
        if not isinstance(profile.get('environment references'), dict):
            raise StateError('environment references must be a mapping')
    else:
        for name in ('adapter tool reference', 'failure handling reference', 'reply correlation contract'):
            required_text(profile.get(name), name)
        for name in ('routes', 'workflow event bindings'):
            if not isinstance(profile.get(name), dict):
                raise StateError(name + ' must be a mapping')
        credentials = profile.get('credential references')
        if not isinstance(credentials, list) or any(not isinstance(x, str) or not x.strip() for x in credentials):
            raise StateError('credential references must be a list of reference strings')
        absolute(profile.get('delivery state reference'), 'delivery state reference')
    try:
        json.dumps(profile, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StateError('profile must contain JSON-compatible data') from exc
    return profile

@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / '.runtime-state.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StateError('concurrent writer or interrupted lock: ' + str(path) + '; reconcile before retry') from exc
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps({'pid': os.getpid()}))
        yield
    finally:
        path.unlink()

def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def resolve(state_root, runtime_id, kind):
    root = absolute(str(state_root), 'state root')
    if kind not in KINDS:
        raise StateError('unknown profile kind')
    profile = validate(read_yaml(root / (kind + '.yaml')), kind, runtime_id)
    return {'profile': profile, 'verification': 'schema and runtime identity only',
            'access': 'not checked', 'authorization': 'not evaluated'}

def configure(state_root, runtime_id, kind, profile, expected_revision=None):
    root = absolute(str(state_root), 'state root')
    validate(profile, kind, runtime_id)
    with locked(root):
        target = root / (kind + '.yaml')
        previous = validate(read_yaml(target), kind, runtime_id) if target.exists() else None
        revision = previous['revision'] if previous else None
        if expected_revision != revision:
            raise StateError('revision conflict: expected ' + str(expected_revision) + ', actual ' + str(revision))
        if same_json(previous, profile):
            return {'changed': False, 'revision': revision}
        if revision == profile['revision']:
            raise StateError('cannot replace content at the same revision')
        history = root / 'history' / kind / (profile['revision'] + '.yaml')
        parent = history.with_suffix('.parent.json')
        if parent.exists():
            if json.loads(parent.read_text(encoding='utf-8')) != {'previous revision': revision}:
                raise StateError('cannot reuse a historical revision')
        elif history.exists():
            raise StateError('historical revision has no matching pending transaction')
        else:
            # Immutable predecessor makes interrupted writes replayable without permitting rollback.
            atomic_write(parent, json.dumps({'previous revision': revision}))
        if history.exists():
            if not same_json(read_yaml(history), profile):
                raise StateError('revision already exists with different content')
        else:
            atomic_write(history, yaml.safe_dump(profile, allow_unicode=True, sort_keys=False))
        if previous:
            old = root / 'history' / kind / (revision + '.yaml')
            if not old.exists():
                atomic_write(old, yaml.safe_dump(previous, allow_unicode=True, sort_keys=False))
        atomic_write(target, yaml.safe_dump(profile, allow_unicode=True, sort_keys=False))
        return {'changed': True, 'revision': profile['revision']}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--runtime-id', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('configure', 'resolve'):
        item = sub.add_parser(command)
        item.add_argument('--kind', choices=KINDS, required=True)
        if command == 'configure':
            item.add_argument('--input', required=True)
            item.add_argument('--expected-revision')
    args = parser.parse_args(argv)
    try:
        result = configure(args.state_root, args.runtime_id, args.kind, read_yaml(args.input), args.expected_revision) if args.command == 'configure' else resolve(args.state_root, args.runtime_id, args.kind)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (StateError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
