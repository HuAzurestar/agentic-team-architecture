#!/usr/bin/env python3
"""Authenticated followup status commit for one actually applied point decision."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from types import MappingProxyType
sys.dont_write_bytecode = True
import context_loader as loader
import task_context as tc
import task_state as writer
import selection_context as selection
import decision_host as human
from decision_commit import git, require, CommitError, PointRequest
from decision_apply import observe_application, references, read_ref
from decision_evidence import canonical, decision_digest, MAX_BYTES
from decision_source import _point
from decision_point import render_decision
from state_prepared import _status_identity


def status_refs(feature, point_id, digest):
    suffix = references(feature, point_id, digest)[0].rsplit("/", 1)[1]
    return "refs/lfd/point-status/" + suffix, "refs/lfd/point-status-applications/" + suffix


def replace_document_set(documents, changes):
    records = dict(documents.records)
    for name, text in changes.items():
        raw = text.encode("utf-8")
        records[name] = replace(records[name], text=text, content_digest=hashlib.sha256(raw).hexdigest(),
                                byte_count=len(raw), newline="LF")
    return replace(documents, records=MappingProxyType(records),
        read_set=replace(documents.read_set,
            documents=tuple(sorted((name, item.content_digest) for name, item in records.items())),
            total_bytes=sum(item.byte_count for item in records.values())))


class PointStatus:
    """Host callbacks remain mandatory after process loss; Git is not authority."""

    def __init__(self, root, repository, point_id, digest, *, source_key, read_reply,
                 interpret, read_grant, repo_overrides=None, next_status=None, recorded_at=None):
        self.root, self.repo = Path(root).resolve(strict=True), Path(repository).resolve(strict=True)
        self.point_id, self.digest, self.source_key = point_id, digest, source_key
        self.overrides = dict(repo_overrides or {})
        require(all(callable(value) for value in (read_reply, interpret, read_grant)), "HUMAN_SOURCE_UNAVAILABLE")
        self.read_reply, self.interpret, self.read_grant = read_reply, interpret, read_grant
        observed = observe_application(self.root, self.repo, point_id, digest)
        require(observed["status"] == "APPLIED_PENDING_STATUS", "POINT_NOT_APPLIED")
        self.decision, self.base = observed["commit"], observed["base"]
        require(observed["head"] == self.decision, "STATUS_HEAD_MOVED")
        self.retained, self.dispatch = status_refs(self.root.name, point_id, digest)
        self.documents = loader.load_feature(loader.LocalMarkdownLoader(self.root))
        self.files = selection.file_snapshot(self.root)
        self.repositories = tc.resolve_repositories(self.root,
            tc.repository_registry(self.documents.read("STATUS.md")), self.overrides)
        owners = [name for name, item in self.repositories.items() if item["role"] == "project-management"
                  and Path(item["path"]).resolve() == self.repo]
        require(len(owners) == 1, "POINT_REPOSITORY_MISMATCH")
        self.management = owners[0]
        self.repo_state = selection.repo_snapshot(self.root, self.repositories)
        self.document = "REQUIREMENT.md" if point_id.startswith("REQ-") else "SOLUTION.md"
        current = self._blob(self.decision, self.document)
        found = []
        for line in _point(current, point_id).splitlines():
            if line.startswith("{"):
                value = json.loads(line)
                if isinstance(value, dict) and value.get("schema") == "decision-evidence-v1":
                    if decision_digest(value) == digest:
                        found.append(value)
        require(len(found) == 1, "POINT_DECISION_RECORD_AMBIGUOUS")
        self.record = found[0]
        require(self.record["feature"] == self.root.name and self.record["exact_scope"] == [point_id]
                and self.record["decision_kind"] == "point", "POINT_SCOPE_MISMATCH")
        self.request = PointRequest(self.root.name, point_id, source_key, self.base, digest)
        self._material()
        old_candidate = read_ref(self.repo, self.retained)
        if old_candidate is not None:
            message = git(self.repo, "show", "-s", "--format=%B", old_candidate)[1].decode("utf-8")
            dates = re.findall(r"^Recorded-At: (.+)$", message, re.M)
            require(len(dates) == 1 and (recorded_at is None or recorded_at == dates[0]), "STATUS_REF_CONFLICT")
            recorded_at = dates[0]
        self.recorded_at = recorded_at or datetime.now(timezone.utc).isoformat()
        date = datetime.fromisoformat(self.recorded_at)
        require(date.tzinfo is not None and date.utcoffset() is not None, "INVALID_RECORDED_AT")
        self.next_status = next_status
        if next_status is not None:
            require(isinstance(next_status, str) and len(next_status.encode("utf-8")) <= MAX_BYTES
                    and _status_identity(next_status) == _status_identity(self.documents.read("STATUS.md")),
                    "STATUS_IDENTITY_CHANGED")
        self.changes = self._changes()
        self._validate()

    def _blob(self, sha, name):
        path = (self.root / name).relative_to(self.repo).as_posix()
        raw = git(self.repo, "show", sha + ":" + path)[1]
        require(len(raw) <= MAX_BYTES, "RESOURCE_LIMIT")
        return raw.decode("utf-8").replace("\r\n", "\n")

    def _material(self):
        before = [self._blob(self.base, name) for name in ("REQUIREMENT.md", "SOLUTION.md")]
        draft = render_decision(*before, self.record)
        require(draft.after == self._blob(self.decision, draft.document), "POINT_COMMIT_SCOPE_MISMATCH")
        return dict(feature=self.root.name, decision_kind="point", exact_scope=[self.point_id],
                    target_ref=dict(source_key=self.source_key, version_kind="git", version=self.base),
                    body=_point(before[0 if self.point_id.startswith("REQ-") else 1], self.point_id))

    def _changes(self):
        original = self.documents.read("TASKS.md")
        records = tc.task_records(original)
        prior = records[self.point_id]
        detail, refs = tc.task_detail(self.root, prior, text=self.documents.read(f"tasks/{self.point_id}.md"))
        reopen = self.record["outcome"] == "REOPENED"
        require(prior["state"] in ({"DONE"} if reopen else {"WIP", "RECORDING"}), "POINT_STATUS_SOURCE_INVALID")
        heads = {}
        previous_refs = deepcopy(refs)
        for item in refs:
            repo = self.repositories.get(item["repository"])
            require(repo is not None, "POINT_REPOSITORY_MISMATCH")
            head = self.decision if item["repository"] == self.management else repo["actual_head"]
            heads[item["repository"]] = head
            start = item["start_refs"]
            if reopen:
                token = repo["actual_branch"] + "@" + head
                if token not in [value.strip() for value in start.split(";")]:
                    start += "; " + token
            values = [item["repository"], repo["actual_branch"], item["baseline_history"], start, head,
                      "-" if reopen else head]
            pattern = re.compile(r"^\|[ \t]*" + re.escape(item["repository"]) + r"[ \t]*\|[^\n]*$", re.M)
            require(len(pattern.findall(detail)) == 1, "POINT_TASK_LAYOUT")
            detail = pattern.sub(lambda match: "| " + " | ".join(values) + " |", detail)
        require(self.management in heads, "POINT_REPOSITORY_MISMATCH")
        head_value = "; ".join(name + "@" + sha for name, sha in heads.items())
        reason = "Decision " + self.record["decision_id"] + " reopened " + self.point_id
        if reopen:
            pattern = re.compile(r"^- Reopen reason[:：][ \t]*.*$", re.M)
            require(len(pattern.findall(detail)) <= 1, "POINT_TASK_LAYOUT")
            detail = pattern.sub("- Reopen reason: " + reason, detail) if pattern.search(detail) else detail.rstrip() + "\n\n- Reopen reason: " + reason + "\n"
        targets = ["WIP"] if reopen else (["RECORDING", "DONE"] if prior["state"] == "WIP" else ["DONE"])
        tasks = original
        for target in targets:
            argv = [str(self.root), self.point_id, "--to", target, "--head", head_value]
            if reopen:
                argv += ["--reason", reason, "--started-at", self.recorded_at]
            elif target == "DONE":
                argv += ["--completed-at", self.recorded_at]
            tasks = writer.transition_text(tasks, writer.parse_args(argv))
        history = dict(decision_commit=self.decision, decision_digest=self.digest, recorded_at=self.recorded_at,
                       source_state=prior["state"], transitions=targets, previous_refs=previous_refs,
                       previous_started_at=prior["started_at"], previous_completed_at=prior["completed_at"])
        detail = detail.rstrip() + "\n\n### Point status history\n\n~~~json\n" + canonical(history).decode("utf-8") + "\n~~~\n"
        changes = {"TASKS.md": tasks, f"tasks/{self.point_id}.md": detail}
        if self.next_status is not None and self.next_status != self.documents.read("STATUS.md"):
            changes["STATUS.md"] = self.next_status
        require(sum(len(text.encode("utf-8")) for text in changes.values()) <= MAX_BYTES, "RESOURCE_LIMIT")
        return changes

    def _validate(self):
        require(selection.file_snapshot(self.root) == self.files
                and selection.repo_snapshot(self.root, self.repositories) == self.repo_state, "POINT_SOURCE_CHANGED")
        require(self.changes == self._changes(), "POINT_STATUS_CHANGED")
        current = loader.load_feature(loader.LocalMarkdownLoader(self.root))
        projected = replace_document_set(current, self.changes)
        outer = self
        class ProjectedProbe:
            def validate(self, actual, records, details):
                # Bind the unchanged physical documents to real Git first.
                # Only task metadata is projected; no dirty-file exemption.
                repositories, _, _ = tc.LocalGitProbe(outer.root, outer.overrides).validate(
                    current, records, details)
                edges = tc.validate_status_repositories(actual.read("STATUS.md"),
                    outer.root / "STATUS.md", repositories)
                trace = tc.validate_trace_graph(actual.read("STATUS.md"), records, details,
                                               repositories, edges)
                from review_resume import recover
                reviews = {}
                for task, (detail, _) in details.items():
                    resumed = recover(actual, detail, records, repositories, tc.commit_exists, task)
                    if resumed is not None:
                        reviews[task] = resumed
                return repositories, trace, reviews
        tc.validate_feature(projected, ProjectedProbe())
        require(selection.file_snapshot(self.root) == self.files
                and selection.repo_snapshot(self.root, self.repositories) == self.repo_state, "POINT_SOURCE_CHANGED")

    def _verify(self):
        try:
            require(decision_digest(self.record) == self.digest, "POINT_DECISION_CHANGED")
            grant = deepcopy(self.read_grant(self.request, deepcopy(self.record)))
            require(type(grant) is human.HumanGrant, "HUMAN_AUTHORITY_UNVERIFIED")
            result = human.inspect_decision(self.record, read_current=self._material, read_reply=self.read_reply,
                                            interpret=self.interpret, grant=grant)
            require(result["applicable"] and result["source_verified"],
                    result["reason_codes"][0] if result["reason_codes"] else "POINT_DECISION_UNVERIFIED")
            require(self.read_grant(self.request, deepcopy(self.record)) == grant, "HUMAN_AUTHORITY_CHANGED")
            observed = observe_application(self.root, self.repo, self.point_id, self.digest)
            require(observed["effect"] == "APPLIED" and observed["head"] == self.decision, "POINT_SOURCE_CHANGED")
            self._validate()
        except CommitError:
            raise
        except Exception:
            raise CommitError("POINT_STATUS_SOURCE_UNAVAILABLE") from None

    def _candidate(self):
        self._verify()
        message = (f"{self.root.name}/{self.point_id}: record {self.record['outcome']} decision status\n\n"
                   f"Decision-Digest: {self.digest}\nDecision-Commit: {self.decision}\nRecorded-At: {self.recorded_at}")
        with tempfile.TemporaryDirectory(prefix="lfd-point-status-") as temporary:
            index = Path(temporary) / "index"
            git(self.repo, "read-tree", self.decision, index=index)
            for name, text in self.changes.items():
                relative = (self.root / name).relative_to(self.repo).as_posix()
                entry = git(self.repo, "ls-tree", "-z", self.decision, "--", relative)[1]
                header, path = entry.rstrip(b"\0").split(b"\t")
                mode, kind, original_blob = header.decode().split()
                require(mode in {"100644", "100755"} and kind == "blob" and path.decode() == relative, "UNSAFE_PATH")
                original = git(self.repo, "cat-file", "blob", original_blob)[1]
                require(b"\r" not in original.replace(b"\r\n", b"")
                        and not (b"\r\n" in original and b"\n" in original.replace(b"\r\n", b"")), "POINT_LINE_ENDINGS")
                raw = text.encode("utf-8")
                if b"\r\n" in original:
                    raw = raw.replace(b"\n", b"\r\n")
                blob = git(self.repo, "hash-object", "-w", "--stdin", data=raw)[1].decode().strip()
                git(self.repo, "update-index", "--cacheinfo", mode, blob, relative, index=index)
            tree = git(self.repo, "write-tree", index=index)[1].decode().strip()
            sha = read_ref(self.repo, self.retained)
            if sha is None:
                sha = git(self.repo, "commit-tree", tree, "-p", self.decision, "-m", message)[1].decode().strip()
            require(git(self.repo, "show", "-s", "--format=%P", sha)[1].decode().strip() == self.decision
                    and git(self.repo, "rev-parse", sha + "^{tree}")[1].decode().strip() == tree
                    and git(self.repo, "show", "-s", "--format=%B", sha)[1].decode().strip() == message, "STATUS_REF_CONFLICT")
            self._verify()
            if read_ref(self.repo, self.retained) is None:
                try:
                    git(self.repo, "update-ref", self.retained, sha, "0" * len(sha))
                except CommitError:
                    require(read_ref(self.repo, self.retained) == sha, "STATUS_REF_UNCONFIRMED")
            require(read_ref(self.repo, self.retained) == sha, "STATUS_REF_CONFLICT")
            return sha

    def apply(self):
        sha = self._candidate()
        sent = read_ref(self.repo, self.dispatch)
        require(sent in (None, sha), "STATUS_REF_CONFLICT")
        if sent is not None:
            return observe_status(self.root, self.repo, self.point_id, self.digest, self.overrides)
        self._verify()
        try:
            git(self.repo, "update-ref", self.dispatch, sha, "0" * len(sha))
        except CommitError:
            return observe_status(self.root, self.repo, self.point_id, self.digest, self.overrides)
        self._verify()
        try:
            git(self.repo, "merge", "--ff-only", "--no-edit", "--no-stat", "--no-autostash", sha)
        except CommitError:
            return observe_status(self.root, self.repo, self.point_id, self.digest, self.overrides)
        return observe_status(self.root, self.repo, self.point_id, self.digest, self.overrides)


def verify_status_content(root, repo, point, candidate, point_id, digest, documents, repositories):
    """Rebuild exact task metadata from its committed parent, without authority."""
    operation = PointStatus.__new__(PointStatus)
    operation.root, operation.repo = root, repo
    operation.point_id, operation.digest = point_id, digest
    operation.decision, operation.base = point["commit"], point["base"]
    name = "REQUIREMENT.md" if point_id.startswith("REQ-") else "SOLUTION.md"
    matches = []
    for line in _point(operation._blob(operation.decision, name), point_id).splitlines():
        if line.startswith("{"):
            value = json.loads(line)
            if isinstance(value, dict) and value.get("schema") == "decision-evidence-v1":
                if decision_digest(value) == digest:
                    matches.append(value)
    require(len(matches) == 1, "POINT_DECISION_RECORD_AMBIGUOUS")
    operation.record = matches[0]
    operation.source_key = operation.record["target_ref"]["source_key"]
    operation._material()
    message = git(repo, "show", "-s", "--format=%B", candidate)[1].decode("utf-8").strip()
    dates = re.findall(r"^Recorded-At: (.+)$", message, re.M)
    require(len(dates) == 1, "STATUS_REF_CONFLICT")
    operation.recorded_at = dates[0]
    date = datetime.fromisoformat(dates[0])
    require(date.tzinfo is not None and date.utcoffset() is not None, "INVALID_RECORDED_AT")
    expected_message = (f"{root.name}/{point_id}: record {operation.record['outcome']} decision status\n\n"
                        f"Decision-Digest: {digest}\nDecision-Commit: {point['commit']}\nRecorded-At: {dates[0]}")
    require(message == expected_message, "STATUS_REF_CONFLICT")
    names = ["TASKS.md", f"tasks/{point_id}.md", "STATUS.md"]
    before = {name: operation._blob(operation.decision, name) for name in names}
    after = {name: operation._blob(candidate, name) for name in names}
    operation.documents = replace_document_set(documents, before)
    require(_status_identity(before["STATUS.md"]) == _status_identity(after["STATUS.md"]),
            "STATUS_IDENTITY_CHANGED")
    operation.next_status = after["STATUS.md"]
    operation.repositories = deepcopy(repositories)
    owners = [name for name, item in repositories.items()
              if item["role"] == "project-management" and Path(item["path"]).resolve() == repo]
    require(len(owners) == 1, "POINT_REPOSITORY_MISMATCH")
    operation.management = owners[0]
    record = tc.task_records(after["TASKS.md"])[point_id]
    _, refs = tc.task_detail(root, record, text=after[f"tasks/{point_id}.md"])
    for item in refs:
        require(item["repository"] in operation.repositories, "POINT_REPOSITORY_MISMATCH")
        # Non-management historical refs are checked by the full trace reader.
        # The management ref is independently forced to the point decision SHA.
        repository = operation.repositories[item["repository"]]
        repository["actual_head"], repository["actual_branch"] = item["head_sha"], item["branch"]
    expected = before | operation._changes()
    require(after == expected, "STATUS_CONTENT_MISMATCH")


def observe_status(root, repository, point_id, digest, repo_overrides=None):
    """Read-only recovery. Completion is verified against the actual full feature."""
    root, repo = Path(root).resolve(strict=True), Path(repository).resolve(strict=True)
    point = observe_application(root, repo, point_id, digest)
    retained, dispatch = status_refs(root.name, point_id, digest)
    candidate, sent = read_ref(repo, retained), read_ref(repo, dispatch)
    result = dict(effect="UNKNOWN", status="STATUS_UNCONFIRMED", decision_commit=point["commit"],
                  status_commit=candidate, task_status_recorded=False, merge_authorized=False)
    require(candidate is not None and sent in (None, candidate), "STATUS_REF_CONFLICT")
    require(git(repo, "show", "-s", "--format=%P", candidate)[1].decode().strip() == point["commit"],
            "STATUS_REF_CONFLICT")
    head = git(repo, "rev-parse", "HEAD")[1].decode().strip()
    if head == point["commit"]:
        result["status"] = "STATUS_DISPATCHED_UNCONFIRMED" if sent else "STATUS_PREPARED"
        return result
    if point["effect"] != "APPLIED" or git(repo, "merge-base", "--is-ancestor", candidate, head, accepted=(0, 1))[0]:
        result["status"] = "STATUS_HEAD_DIVERGED"
        return result
    changed = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", point["commit"], candidate)[1]
    relative_root = root.relative_to(repo).as_posix() + "/"
    expected = {relative_root + "TASKS.md", relative_root + f"tasks/{point_id}.md"}
    paths = set(changed.decode("utf-8").rstrip("\0").split("\0"))
    require(expected <= paths <= expected | {relative_root + "STATUS.md"}, "STATUS_COMMIT_SCOPE_MISMATCH")
    for path in paths:
        if git(repo, "ls-tree", "-z", candidate, "--", path)[1] != git(repo, "ls-tree", "-z", head, "--", path)[1]:
            result["status"] = "STATUS_CONTENT_CHANGED"
            return result
    documents = loader.load_feature(loader.LocalMarkdownLoader(root))
    feature = tc.validate_feature(documents, tc.LocalGitProbe(root, repo_overrides or {}))
    verify_status_content(root, repo, point, candidate, point_id, digest, documents, feature.repositories)
    require(git(repo, "rev-parse", "HEAD")[1].decode().strip() == head
            and read_ref(repo, retained) == candidate and read_ref(repo, dispatch) == sent, "POINT_SOURCE_CHANGED")
    result.update(effect="APPLIED", status="STATUS_RECORDED", task_status_recorded=True)
    return result
