#!/usr/bin/env python3
"""Authenticated single-point commit preparation, not branch/task application.

Retained refs survive process loss. A later coordinator must apply this exact
commit and record its SHA through the task writer. No merge/push or task DONE.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
import task_context as tc
import selection_context as selection
from context_loader import LocalMarkdownLoader, load_feature
import quality_source as sources
import decision_source
import decision_host as human
from decision_evidence import MAX_BYTES, canonical, decision_digest
from decision_point import render_decision


class CommitError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise CommitError(code)


def git(repo, *args, index=None, data=None, accepted=(0,)):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    require(data is None or len(data) <= MAX_BYTES, "RESOURCE_LIMIT")
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(["git", "--no-pager", "--literal-pathspecs", "-C", str(repo), *args],
                                    input=data, env=env, stdout=output, stderr=subprocess.DEVNULL, timeout=50)
            require(result.returncode in accepted, "POINT_GIT_FAILED")
            require(output.tell() <= MAX_BYTES, "RESOURCE_LIMIT")
            output.seek(0)
            return result.returncode, output.read(MAX_BYTES + 1)
    except (OSError, subprocess.TimeoutExpired):
        raise CommitError("POINT_GIT_UNAVAILABLE") from None


@dataclass(frozen=True)
class PointRequest:
    feature: str
    point_id: str
    source_key: str
    base: str
    decision_digest: str


class PointCommit:
    """Configured Python host API. Nothing here loads callbacks from evidence."""

    def __init__(self, root, point_id, record, *, source_key, read_reply, interpret,
                 read_grant, repo_overrides=None):
        self.root = Path(root).resolve(strict=True)
        self.overrides = dict(repo_overrides or {})
        require(all(callable(value) for value in (read_reply, interpret, read_grant)),
                "HUMAN_SOURCE_UNAVAILABLE")
        self.read_reply, self.interpret, self.read_grant = read_reply, interpret, read_grant
        digest = decision_digest(record)
        self.record = json.loads(canonical(record))
        require(self.record["feature"] == self.root.name and self.record["decision_kind"] == "point"
                and self.record["exact_scope"] == [point_id], "POINT_SCOPE_MISMATCH")
        self.files = selection.file_snapshot(self.root)
        self.feature = self._feature()
        self.refs = selection.repo_snapshot(self.root, self.feature.repositories)
        require(selection.file_snapshot(self.root) == self.files, "POINT_SOURCE_CHANGED")
        task = self.feature.records.get(point_id)
        require(task is not None, "POINT_TASK_MISSING")
        require(task["state"] in ({"DONE"} if self.record["outcome"] == "REOPENED" else {"WIP", "RECORDING"}),
                "POINT_TASK_NOT_READY")
        owners = [repo for repo in self.feature.repositories.values() if repo["role"] == "project-management"
                  and self.root.is_relative_to(Path(repo["path"]))]
        require(len(owners) == 1, "POINT_REPOSITORY_MISMATCH")
        owner = owners[0]
        self.repo, self.base = Path(owner["path"]).resolve(), owner["actual_head"]
        self.request = PointRequest(self.root.name, point_id, source_key, self.base, digest)
        self.bindings = tuple(sources.GitDocument(name, self.repo, (self.root / name).relative_to(self.repo).as_posix(),
                                                self.base) for name in ("REQUIREMENT.md", "SOLUTION.md"))
        self.snapshot = sources.read_git_documents(self.bindings)
        docs = {key: value.decode("utf-8").replace("\r\n", "\n") for key, value in self.snapshot.documents.items()}
        self.draft = render_decision(docs["REQUIREMENT.md"], docs["SOLUTION.md"], self.record)
        self.path = (self.root / self.draft.document).relative_to(self.repo).as_posix()
        key = canonical(dict(feature=self.root.name, point_id=point_id, decision_digest=digest))
        self.retained_ref = "refs/lfd/point-decisions/" + hashlib.sha256(key).hexdigest()
        self._unchanged()

    def _feature(self):
        return tc.validate_feature(load_feature(LocalMarkdownLoader(self.root)), tc.LocalGitProbe(self.root, self.overrides))

    def _unchanged(self):
        # Full recovery checks include hidden index flags, refs and Git identity.
        current = self._feature()
        require(current.repositories == self.feature.repositories
                and selection.file_snapshot(self.root) == self.files
                and selection.repo_snapshot(self.root, current.repositories) == self.refs,
                "POINT_SOURCE_CHANGED")
        require(sources.read_git_documents(self.bindings) == self.snapshot, "POINT_SOURCE_CHANGED")

    def _verify(self):
        try:
            self._verify_inputs()
        except CommitError:
            raise
        except Exception:
            # Provider diagnostics can contain tokens or complete replies.
            raise CommitError("POINT_SOURCE_UNAVAILABLE") from None

    def _verify_inputs(self):
        require(decision_digest(self.record) == self.request.decision_digest, "POINT_DECISION_CHANGED")
        self._draft_unchanged()
        grant = deepcopy(self.read_grant(self.request, deepcopy(self.record)))
        require(type(grant) is human.HumanGrant, "HUMAN_AUTHORITY_UNVERIFIED")
        def current():
            return decision_source.read_git_current(self.repo, self.path, source_key=self.request.source_key,
                feature=self.request.feature, decision_kind="point", exact_scope=[self.request.point_id],
                expected_head=self.base)
        result = human.inspect_decision(self.record, read_current=current, read_reply=self.read_reply,
                                        interpret=self.interpret, grant=grant)
        require(result["applicable"] and result["source_verified"],
                result["reason_codes"][0] if result["reason_codes"] else "POINT_DECISION_UNVERIFIED")
        require(self.read_grant(self.request, deepcopy(self.record)) == grant, "HUMAN_AUTHORITY_CHANGED")
        # Last callback may have changed files, HEAD, index flags or a repository.
        self._unchanged()
        self._draft_unchanged()

    def _draft_unchanged(self):
        docs = {key: value.decode("utf-8").replace("\r\n", "\n") for key, value in self.snapshot.documents.items()}
        expected = render_decision(docs["REQUIREMENT.md"], docs["SOLUTION.md"], self.record)
        key = canonical(dict(feature=self.root.name, point_id=self.request.point_id,
                             decision_digest=self.request.decision_digest))
        require(self.draft == expected and self.base == self.request.base
                and self.path == (self.root / expected.document).relative_to(self.repo).as_posix()
                and self.retained_ref == "refs/lfd/point-decisions/" + hashlib.sha256(key).hexdigest(),
                "POINT_DRAFT_CHANGED")

    def _existing(self):
        code, raw = git(self.repo, "rev-parse", "--verify", "--quiet", self.retained_ref, accepted=(0, 1))
        if code:
            return None
        sha = raw.decode("ascii").strip()
        require(sources.SHA.fullmatch(sha), "POINT_REF_CONFLICT")
        return sha

    def _validate_commit(self, sha, tree, message):
        require(git(self.repo, "show", "-s", "--format=%P", sha)[1].decode().strip() == self.base
                and git(self.repo, "rev-parse", sha + "^{tree}")[1].decode().strip() == tree
                and git(self.repo, "show", "-s", "--format=%B", sha)[1].decode().strip() == message.strip(),
                "POINT_REF_CONFLICT")
        changed = git(self.repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", self.base, sha)[1]
        require(changed == self.path.encode("utf-8") + b"\0", "POINT_COMMIT_SCOPE_MISMATCH")

    def prepare_commit(self):
        """Persist one authenticated candidate; leaves HEAD/index/worktree intact.

        Same decision digest reuses its retained commit after revalidation.
        Unknown update-ref outcomes are read back, never blindly dispatched twice.
        Creating objects before a refusal can leave unreachable Git objects, not
        an applied decision. This API intentionally does not complete any task.
        """
        self._verify()
        message = (f"{self.request.feature}/{self.request.point_id}: {self.record['outcome']} record human decision\n\n"
                   f"Decision-Digest: {self.request.decision_digest}\nPrepared-From: {self.base}")
        with tempfile.TemporaryDirectory(prefix="lfd-point-index-") as temporary:
            index = Path(temporary) / "index"
            git(self.repo, "read-tree", self.base, index=index)
            entry = git(self.repo, "ls-tree", "-z", self.base, "--", self.path)[1]
            header, name = entry.rstrip(b"\0").split(b"\t")
            mode, kind, original_blob = header.decode().split()
            require(mode in {"100644", "100755"} and kind == "blob" and name.decode() == self.path,
                    "POINT_SOURCE_CHANGED")
            original = git(self.repo, "cat-file", "blob", original_blob)[1]
            # Preserve a consistently CRLF Git blob; mixed raw endings need an
            # explicit migration instead of silently changing unrelated lines.
            require(b"\r" not in original.replace(b"\r\n", b""), "POINT_LINE_ENDINGS")
            require(not (b"\r\n" in original and b"\n" in original.replace(b"\r\n", b"")), "POINT_LINE_ENDINGS")
            after = self.draft.after.encode("utf-8")
            if b"\r\n" in original:
                after = after.replace(b"\n", b"\r\n")
            blob = git(self.repo, "hash-object", "-w", "--stdin", data=after)[1].decode().strip()
            git(self.repo, "update-index", "--cacheinfo", mode, blob, self.path, index=index)
            tree = git(self.repo, "write-tree", index=index)[1].decode().strip()
            sha = self._existing()
            reused = sha is not None
            if sha is None:
                sha = git(self.repo, "commit-tree", tree, "-p", self.base, "-m", message)[1].decode().strip()
            self._validate_commit(sha, tree, message)
            self._verify()
            if not reused:
                try:
                    git(self.repo, "update-ref", self.retained_ref, sha, "0" * len(sha))
                except CommitError:
                    # Response loss is not a reason to issue another write.
                    if self._existing() != sha:
                        raise CommitError("POINT_REF_UNCONFIRMED") from None
            require(self._existing() == sha, "POINT_REF_CONFLICT")
        return dict(effect="COMMIT_PREPARED", application="NOT_APPLIED", commit=sha,
                    retained_ref=self.retained_ref, base=self.base, point_id=self.request.point_id,
                    reused=reused, merge_authorized=False)
