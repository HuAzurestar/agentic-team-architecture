"""Gitee Issues and Pull Requests adapter (API v5)."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.core.logging import get_logger


class GiteeProvider:
    name = "gitee"

    def __init__(self, config: dict):
        self.url = config.get("api_url", "https://gitee.com/api/v5").rstrip("/")
        self.token = config.get("token", "")
        self.logger = get_logger()

    def _request(self, method, path, payload=None):
        self.logger.info("api_request provider=gitee method=%s path=%s", method, path)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        # Gitee API v5 accepts access_token as a query parameter.
        separator = "&" if "?" in path else "?"
        request = Request(self.url + path + separator + "access_token=" + self.token, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                self.logger.info("api_response provider=gitee method=%s path=%s status=%s", method, path, response.status)
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            self.logger.error("api_error provider=gitee method=%s path=%s status=%s detail=%s", method, path, exc.code, detail)
            raise RuntimeError(f"Gitee API {exc.code} for {method} {path}: {detail}") from exc

    @staticmethod
    def _repo(value):
        return value.rsplit("#", 1)

    def fetch(self, document):
        key = document.sync.primary
        repo, number = self._repo(document.platform_ids[key])
        owner, name = repo.split("/", 1)
        if key == "gitee_issue":
            data = self._request("GET", f"/repos/{owner}/{name}/issues/{number}")
            repository_data = data.get("repository") or {}
            data["_sync_pull_requests"] = self._request("GET", f"/repos/{owner}/issues/{number}/pull_requests?repo={name}")
            body = data.get("body") or ""
            data["repository"] = {"full_name": repo}
            data["_sync_connected_prs"] = data.pop("_sync_pull_requests", [])
            data["state"] = data.get("issue_state") or data.get("state")
            data["labels"] = data.get("labels") or []
            data["assignees"] = repository_data.get("assignee") or []
            if data.get("issue_type"):
                data["type"] = data["issue_type"]
            data["_sync_parent_issue"] = None
            data["_sync_sub_issues"] = []
        elif key == "gitee_pull_request":
            data = self._request("GET", f"/repos/{owner}/{name}/pulls/{number}")
            data["_sync_commits"] = self._request("GET", f"/repos/{owner}/{name}/pulls/{number}/commits")
            body = data.get("body") or ""
            data["repository"] = {"full_name": repo}
            data["_sync_development"] = {"commits": data["_sync_commits"], "reviewers": {"users": []}, "checks": [], "deployments": []}
        else:
            raise ValueError("unsupported Gitee ID")
        data["_sync_repository"] = repo
        return data, body

    def create(self, document, object_type, repository):
        owner, name = repository.split("/", 1)
        key = "gitee_issue" if object_type == "issue" else "gitee_pull_request"
        platform = document.metadata.get("platform", {}).get(key, {})
        title = platform.get("title") or document.metadata.get("title") or document.path.stem
        if object_type == "issue":
            # Gitee's create-Issue endpoint keeps the repository in a query
            # parameter, unlike GitHub's /repos/{owner}/{repo}/issues.
            data = self._request("POST", f"/repos/{owner}/issues?repo={name}", {"title": title, "body": document.body})
        else:
            head = platform.get("head_branch")
            base = platform.get("base_branch")
            if not head or not base:
                raise ValueError("Gitee Pull Request upload requires head_branch and base_branch")
            data = self._request("POST", f"/repos/{owner}/{name}/pulls", {"title": title, "body": document.body, "head": head, "base": base})
        return {"id": f"{repository}#{data['number']}", "number": data["number"], "title": data.get("title") or data.get("name")}

    def update(self, document, body, joint=False):
        for key in ("gitee_issue", "gitee_pull_request"):
            remote = document.platform_ids.get(key)
            if not remote:
                continue
            repo, number = self._repo(remote)
            owner, name = repo.split("/", 1)
            platform = document.metadata.get("platform", {}).get(key, {})
            payload = {"title": platform.get("title") or document.path.stem, "body": body}
            self.logger.info("sync_payload provider=gitee target=%s fields=%s joint=%s", remote, list(payload), joint)
            path = f"/repos/{owner}/issues/{number}?repo={name}" if key == "gitee_issue" else f"/repos/{owner}/{name}/pulls/{number}"
            self._request("PATCH", path, payload)
