"""GitHub Issues and Pull Requests provider."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from src.core.document import MarkdownDocument
from src.core.logging import get_logger


class GitHubProvider:
    """GitHub Issues and Pull Requests adapter using the REST API."""
    name = "github"

    def __init__(self, config: dict):
        self.url = config.get("api_url", "https://api.github.com").rstrip("/")
        self.token = config.get("token", "")
        self.logger = get_logger()

    def _request(self, method, path, payload=None):
        self.logger.info("api_request provider=github method=%s path=%s", method, path)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        if data is not None: headers["Content-Type"] = "application/json"
        request = Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                self.logger.info("api_response provider=github method=%s path=%s status=%s", method, path, response.status)
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            self.logger.error("api_error provider=github method=%s path=%s status=%s detail=%s", method, path, exc.code, detail)
            raise RuntimeError(f"GitHub API {exc.code} for {method} {path}: {detail}") from exc
        except Exception as exc:
            self.logger.exception("api_error provider=github method=%s path=%s error=%s", method, path, exc)
            raise

    def fetch(self, document: MarkdownDocument):
        key = document.sync.primary
        remote = document.platform_ids[key]
        repo, number = remote.rsplit("#", 1)
        if key == "github_issue":
            data = self._request("GET", f"/repos/{repo}/issues/{number}")
            data["_sync_sub_issues"] = self._request("GET", f"/repos/{repo}/issues/{number}/sub_issues")
            timeline = self._request("GET", f"/repos/{repo}/issues/{number}/timeline?per_page=100")
            data["_sync_connected_prs"] = [
                event["subject"] for event in timeline
                if event.get("event") == "connected"
                and event.get("subject", {}).get("type") == "pull_request"
            ]
            try:
                data["_sync_parent_issue"] = self._request("GET", f"/repos/{repo}/issues/{number}/parent")
            except Exception:
                data["_sync_parent_issue"] = None
            data["_sync_development"] = {"pull_requests": [], "branches": [], "commits": []}
        elif key == "github_pull_request":
            data = self._request("GET", f"/repos/{repo}/pulls/{number}")
            commits = self._request("GET", f"/repos/{repo}/pulls/{number}/commits?per_page=100")
            reviewers = self._request("GET", f"/repos/{repo}/pulls/{number}/requested_reviewers")
            sha = data.get("head", {}).get("sha")
            checks = self._request("GET", f"/repos/{repo}/commits/{sha}/check-runs") if sha else {"check_runs": []}
            deployments = self._request("GET", f"/repos/{repo}/deployments?sha={sha}&per_page=100") if sha else []
            data["_sync_development"] = {"commits": commits, "reviewers": reviewers, "checks": checks.get("check_runs", []), "deployments": deployments}
        else:
            raise ValueError("unsupported GitHub ID")
        return data, data.get("body") or ""

    def create(self, document: MarkdownDocument, object_type: str, repository: str):
        platform = document.metadata.get("platform", {}).get(f"github_{object_type}", {})
        title = platform.get("title") or document.metadata.get("title") or document.path.stem
        if object_type == "issue":
            payload = {"title": title, "body": document.body}
            if platform.get("labels"): payload["labels"] = platform["labels"]
            if platform.get("assignees"): payload["assignees"] = platform["assignees"]
            data = self._request("POST", f"/repos/{repository}/issues", payload)
            return {"id": f"{repository}#{data['number']}", "number": data["number"], "title": data["title"]}
        if object_type == "pull_request":
            base = platform.get("base_branch")
            head = platform.get("head_branch")
            if not base or not head:
                raise ValueError("GitHub Pull Request upload requires base_branch and head_branch")
            data = self._request("POST", f"/repos/{repository}/pulls", {"title": title, "body": document.body, "base": base, "head": head, "draft": bool(platform.get("draft", False))})
            return {"id": f"{repository}#{data['number']}", "number": data["number"], "title": data["title"]}
        raise ValueError("unsupported GitHub object type")

    def update(self, document: MarkdownDocument, body: str, joint: bool = False):
        # Public API support is intentionally conservative: title/body are safe
        # by default; relationship and management fields require explicit mode.
        for key in ("github_issue", "github_pull_request"):
            remote = document.platform_ids.get(key)
            if not remote: continue
            repo, number = remote.rsplit("#", 1)
            platform = document.metadata.get("platform", {}).get(key, {})
            payload = {"title": platform.get("title") or document.path.stem, "body": body}
            self.logger.info("sync_payload target=%s fields=%s joint=%s", remote, list(payload), joint)
            if not joint:
                self.logger.info("sync_skip target=%s fields=labels,assignees,state,relations reason=default_safe_mode", remote)
            self._request("PATCH", f"/repos/{repo}/{ 'issues' if key == 'github_issue' else 'pulls' }/{number}", payload)

    def set_parent_issue(self, child_id: str, parent_id: str) -> None:
        child_repo, child_number = child_id.rsplit("#", 1)
        parent_repo, parent_number = parent_id.rsplit("#", 1)
        if child_repo.lower() != parent_repo.lower():
            raise ValueError("GitHub parent and child issues must be in the same repository")
        child = self._request("GET", f"/repos/{child_repo}/issues/{child_number}")
        self._request("POST", f"/repos/{parent_repo}/issues/{parent_number}/sub_issues", {"sub_issue_id": child["id"]})
