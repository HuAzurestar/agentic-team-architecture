#!/usr/bin/env python3
"""Durable workflow event IO. External adapters deliver; this program never sends."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from runtime_state import StateError, absolute, atomic_write, locked, required_text, resolve, same_json

sys.dont_write_bytecode = True

def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StateError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(StateError('invalid JSON constant: ' + value)))
    except (OSError, ValueError) as exc:
        raise StateError('cannot read JSON: ' + str(exc)) from exc

def check_mapping(value):
    if not isinstance(value, dict):
        raise StateError('input must be a JSON object')
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StateError('input must be JSON-compatible') from exc


def require_fields(value, fields):
    check_mapping(value)
    for field in fields:
        required_text(value.get(field), field)


def put(mapping, key, value):
    if key in mapping:
        if not same_json(mapping[key], value):
            raise StateError('immutable identity conflicts with existing payload: ' + key)
        return False
    mapping[key] = value
    return True


def operate(state_root, runtime_id, command, data=None, event_id=None, current_object_revision=None):
    profile = resolve(state_root, runtime_id, 'notification')['profile']
    directory = absolute(profile['delivery state reference'], 'delivery state reference')
    # Lock the actual shared ledger location; profile roots may intentionally refer to it.
    with locked(directory):
        path = directory / 'workflow-events.json'
        ledger = load_json(path) if path.exists() else {'schema': 1, 'runtime identity': runtime_id, 'events': {}}
        if ledger.get('runtime identity') != runtime_id or ledger.get('schema') != 1:
            raise StateError('delivery-state runtime identity or schema mismatch; explicit handoff required')
        if not isinstance(ledger.get('events'), dict):
            raise StateError('invalid event ledger')
        if command == 'inspect':
            if event_id is not None:
                if event_id not in ledger['events']:
                    raise StateError('unknown event id')
                return ledger['events'][event_id]
            return ledger
        check_mapping(data)
        key = required_text(data.get('event id'), 'event id')
        changed = False
        if command == 'record':
            require_fields(data, ('event id', 'event type', 'phase', 'purpose', 'priority', 'feature', 'task',
                                  'object revision', 'occurred at', 'actor', 'correlation id'))
            if type(data.get('decision required')) is not bool:
                raise StateError('decision required must be boolean')
            if data['decision required']:
                required_text(data.get('decider'), 'decider')
                required_text(data.get('requested scope'), 'requested scope')
                required_text(data.get('allowed consequences'), 'allowed consequences')
            if 'payload' not in data:
                raise StateError('payload is required (may be null for explicitly unavailable content)')
            existing = ledger['events'].get(key)
            if existing is not None:
                if not same_json(existing['event'], data):
                    raise StateError('event id conflicts with existing payload')
            else:
                ledger['events'][key] = {'event': data, 'profile revision': profile['revision'],
                                         'attempts': {}, 'replies': {}}
                changed = True
        else:
            if key not in ledger['events']:
                raise StateError('persist event before attempts or replies')
            entry = ledger['events'][key]
            event = entry['event']
            if command == 'attempt':
                require_fields(data, ('event id', 'attempt id', 'occurred at', 'adapter tool reference', 'route'))
                if data['adapter tool reference'] != profile['adapter tool reference']:
                    raise StateError('attempt adapter does not match current profile')
                if data['route'] not in profile['routes']:
                    raise StateError('attempt route is not configured')
                attempt = entry['attempts'].get(data['attempt id'])
                if attempt is not None:
                    if not same_json(attempt['request'], data):
                        raise StateError('attempt id conflicts with existing payload')
                else:
                    entry['attempts'][data['attempt id']] = {'request': data, 'acknowledgement': None}
                    changed = True
            elif command == 'ack':
                require_fields(data, ('event id', 'attempt id', 'occurred at', 'status'))
                if data['status'] not in ('accepted', 'failed', 'unknown'):
                    raise StateError('status must be accepted, failed or unknown')
                attempt = entry['attempts'].get(data['attempt id'])
                if attempt is None:
                    raise StateError('persist attempt before external delivery and acknowledgement')
                if attempt['acknowledgement'] is not None:
                    if not same_json(attempt['acknowledgement'], data):
                        raise StateError('acknowledgement conflict; retain original and use a distinct attempt')
                else:
                    attempt['acknowledgement'] = data
                    changed = True
            elif command == 'reply':
                require_fields(data, ('event id', 'reply id', 'correlation id', 'object revision', 'declared decider',
                                     'original wording', 'source', 'occurred at'))
                required_text(current_object_revision, 'current object revision')
                if not event['decision required']:
                    raise StateError('event does not request a decision')
                if data['correlation id'] != event['correlation id']:
                    raise StateError('reply correlation mismatch')
                if data['object revision'] != event['object revision'] or data['object revision'] != current_object_revision:
                    raise StateError('stale or mismatched object revision')
                if data['declared decider'] != event['decider']:
                    raise StateError('declared decider mismatch; identity authentication is external')
                changed = put(entry['replies'], data['reply id'], data)
            else:
                raise StateError('unknown operation')
        if changed:
            atomic_write(path, json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        return {'changed': changed, 'event id': key, 'persisted': True,
                'delivery': 'not performed by this tool', 'identity authentication': 'not performed',
                'workflow authorization': 'not evaluated'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--runtime-id', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('record', 'attempt', 'ack', 'reply', 'inspect'):
        item = sub.add_parser(name)
        if name == 'inspect':
            item.add_argument('--event-id')
        else:
            item.add_argument('--input', required=True, help='JSON object file')
        if name == 'reply':
            item.add_argument('--current-object-revision', required=True)
    args = parser.parse_args(argv)
    try:
        result = operate(args.state_root, args.runtime_id, args.command,
                         load_json(args.input) if hasattr(args, 'input') else None,
                         getattr(args, 'event_id', None), getattr(args, 'current_object_revision', None))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (StateError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
