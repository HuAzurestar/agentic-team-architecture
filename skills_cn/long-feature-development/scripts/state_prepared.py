"""Exact prepared-metadata reconciliation from a clean, actual Git baseline.

This reads, never prepares or commits files. No serialized validation grant and
no ignore-dirty switch exist. Use one instance for one coordinator operation.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
from types import MappingProxyType
import sys
sys.dont_write_bytecode = True
import context_loader as loader
import task_context as tc
import task_state as writer
import state_guard as guard
from selection_context import file_snapshot, repo_snapshot
from review_source import _run


def require(value, code):
    if not value:
        raise tc.ContextError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _status_identity(text):
    value = tc.focused_status(text)
    # Control summary and task labels can change. Repository identities, heads,
    # integration opponents and PR endpoints cannot change during this write.
    return (tc.repository_registry(text),
            [row[:4] for row in value['working_branches']['rows']],
            value['integration_opponents'], value['pr_mr_objects'])


class PreparedTransition:
    def __init__(self, root, args, changes, *, repo_overrides=None):
        self.root = Path(root).resolve(strict=True)
        self.args = deepcopy(args)
        self.overrides = dict(repo_overrides or {})
        require(type(changes) is dict and set(changes) <= {'STATUS.md', f'tasks/{args.task_id}.md'}
                and all(type(raw) is bytes for raw in changes.values()), 'INVALID_PREPARED_CHANGES')
        require(sum(map(len, changes.values())) <= loader.MAX_BYTES, 'RESOURCE_LIMIT')
        before = file_snapshot(self.root)
        self.feature = tc.validate_feature(loader.load_feature(loader.LocalMarkdownLoader(self.root)),
                                           tc.LocalGitProbe(self.root, self.overrides))
        require(self.feature.trace['mode'] == 'VALIDATED', 'UNVERIFIED_TRACE')
        require(file_snapshot(self.root) == before, 'STATE_SOURCE_CHANGED')
        require(set(changes) <= before.keys(), 'INVALID_PREPARED_CHANGES')
        self.before = before
        self.expected = before | {name: digest(raw) for name, raw in changes.items()}
        self.original = self.feature.documents.read('TASKS.md')
        self.candidate = writer.transition_text(self.original, self.args)
        self.request = guard.TransitionRequest(str(self.root), args.task_id,
            self.feature.records[args.task_id]['state'], args.to,
            digest(self.original.encode('utf-8')), digest(self.candidate.encode('utf-8')),
            tuple(sorted(self.expected.items())))
        self.identity = _status_identity(self.feature.documents.read('STATUS.md'))
        self.edges = tc.validate_status_repositories(self.feature.documents.read('STATUS.md'),
            self.root / 'STATUS.md', self.feature.repositories)
        self.repositories = self._repositories()
        self._check_workspace(None, prepared=False)
        require(file_snapshot(self.root) == before, 'STATE_SOURCE_CHANGED')

    def _repositories(self):
        resolved = tc.resolve_repositories(self.root, tc.repository_registry(
            tc.read_utf8(self.root / 'STATUS.md')), self.overrides)
        require(resolved == self.feature.repositories, 'STATE_REPOSITORY_CHANGED')
        snapshots = repo_snapshot(self.root, self.feature.repositories)
        for name, repo in self.feature.repositories.items():
            # Worktree status is reconciled separately, never discarded globally.
            snapshots[name].pop('status')
            path = Path(repo['path'])
            scope = ['--']
            if repo['role'] == 'project-management':
                scope.append(self.root.relative_to(path).as_posix())
            for option in ('--stage', '-v'):
                snapshots[name][option] = digest(_run(path, 'ls-files', option, '-z',
                                                     *scope, configured=True)[1])
        return snapshots

    def _temporary(self, request):
        temporary = guard._TEMPORARY.get()
        if temporary is None:
            return None
        binding, path, device, inode = temporary
        require(binding == request.digest and path.parent == self.root, 'STATE_TEMPORARY_CHANGED')
        # Exact inode and bytes, not a wildcard allowance for TASKS.*.tmp.
        raw, identity = loader.LocalMarkdownLoader(self.root)._read_raw(path.name, loader.MAX_BYTES)
        require(identity == f'local:{device}:{inode}' and path.stat().st_nlink == 1
                and raw == self.candidate.encode('utf-8'), 'STATE_TEMPORARY_CHANGED')
        return path

    def _check_workspace(self, request, *, prepared=True):
        temporary = self._temporary(request) if request is not None else None
        for repo in self.feature.repositories.values():
            path = Path(repo['path'])
            scope = ['--']
            if repo['role'] == 'project-management':
                prefix = self.root.relative_to(path).as_posix() + '/'
                scope.append(prefix)
                allowed = {prefix + name for name in self.expected
                           if prepared and self.expected[name] != self.before[name]}
                temp_path = temporary.relative_to(path).as_posix() if temporary else None
            else:
                allowed, temp_path = set(), None
            raw = _run(path, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                       *scope, configured=True)[1]
            for entry in raw.split(b'\0'):
                if not entry:
                    continue
                name = entry[3:].decode('utf-8')
                require((entry[:3] == b' M ' and name in allowed)
                        or (entry[:3] == b'?? ' and name == temp_path), 'STATE_UNEXPECTED_WORKSPACE')

    def read(self, request):
        require(type(request) is guard.TransitionRequest and request == self.request,
                'STATE_PREPARATION_MISMATCH')
        require(file_snapshot(self.root) == self.expected, 'STATE_SOURCE_CHANGED')
        require(self._repositories() == self.repositories, 'STATE_REPOSITORY_CHANGED')
        self._check_workspace(request)
        documents = loader.load_feature(loader.LocalMarkdownLoader(self.root))
        require(_status_identity(documents.read('STATUS.md')) == self.identity, 'STATE_REPOSITORY_CHANGED')
        require(documents.read('TASKS.md') == self.original, 'STATE_SOURCE_CHANGED')
        records = dict(documents.records)
        raw = self.candidate.encode('utf-8')
        records['TASKS.md'] = replace(records['TASKS.md'], text=self.candidate,
            content_digest=digest(raw), byte_count=len(raw), newline='LF')
        projected = replace(documents, records=MappingProxyType(records),
            read_set=replace(documents.read_set,
                documents=tuple(sorted((name, record.content_digest) for name, record in records.items())),
                total_bytes=sum(record.byte_count for record in records.values())))
        outer = self

        class PreparedProbe:
            def validate(self, actual, tasks, details):
                # The strict baseline resolved DERIVED:HEAD while STATUS was clean.
                # Its immutable Git columns, refs/config/index and physical files
                # are compared here; no future management commit is invented.
                trace = tc.validate_trace_graph(actual.read('STATUS.md'), tasks, details,
                                               outer.feature.repositories, outer.edges)
                from review_resume import recover
                reviews = {}
                for task, (detail, _) in details.items():
                    result = recover(actual, detail, tasks, outer.feature.repositories, tc.commit_exists, task)
                    if result is not None:
                        reviews[task] = result
                return outer.feature.repositories, trace, reviews

        tc.validate_feature(projected, PreparedProbe())
        require(file_snapshot(self.root) == self.expected, 'STATE_SOURCE_CHANGED')
        require(self._repositories() == self.repositories, 'STATE_REPOSITORY_CHANGED')
        self._check_workspace(request)
        # Consumers must compare the BEFORE graph to the writer's original row.
        # The entire projected AFTER graph has just passed the same validators.
        return self.feature
