"""Synchronization orchestration. Providers are intentionally replaceable."""
from pathlib import Path
import sys

from src.document import parse_file, render_document
from src.document.parser import parse_text
from src.core.result import SyncResult, SyncStatus
from src.controller.metadata import drop_empty
from src.core.logging import get_logger


class SyncController:
    """Select the primary platform and coordinate local/remote operations."""
    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger()
        self.providers = {}
        yt = config.get("providers", {}).get("youtrack", {})
        if yt.get("enabled") and yt.get("token"):
            from src.providers.youtrack import YouTrackProvider
            self.providers["youtrack"] = YouTrackProvider(yt)
        gh = config.get("providers", {}).get("github", {})
        if gh.get("enabled") and gh.get("token"):
            from src.providers.github import GitHubProvider
            self.providers["github"] = GitHubProvider(gh)
        ge = config.get("providers", {}).get("gitee", {})
        if ge.get("enabled") and ge.get("token"):
            from src.providers.gitee import GiteeProvider
            self.providers["gitee"] = GiteeProvider(ge)

    def status(self) -> None:
        print(f"mode: {self.config.get('mode', 'remote_authoritative')}")
        print("providers: " + ", ".join(self.providers) if self.providers else "providers: none")

    def download(self, file: Path, remote: str | None = None) -> None:
        # A missing file may be bootstrapped only from an explicit remote ID.
        if not file.exists():
            if not remote or ":" not in remote:
                raise FileNotFoundError(f"本地文件不存在，请使用 --remote provider:id: {file}")
            provider_name, remote_id = remote.split(":", 1)
            key = provider_name if provider_name in ("youtrack_article", "youtrack_issue", "github_issue", "github_pull_request", "gitee_issue", "gitee_pull_request") else f"{provider_name}_article"
            document = parse_text(f'---\ndoc_type: markdown\nid:\n  {key}: "{remote_id}"\n---\n', file)
        else:
            document = parse_file(file)
            self._require_sync_metadata(document, "download")
        if not document.sync.primary:
            raise ValueError("download requires id with a platform ID")
        provider_name = "github" if document.sync.primary.startswith("github_") else ("gitee" if document.sync.primary.startswith("gitee_") else "youtrack")
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"provider not configured: {provider_name}")
        data, body = provider.fetch(document)
        if not body or not body.strip():
            raise ValueError(f"remote object has no Markdown content; refusing to write {file}")
        metadata = dict(document.metadata)
        ids = dict(metadata.get("id", {}))
        if document.sync.primary == "youtrack_article": ids["youtrack_article"] = data.get("idReadable", data["id"])
        if document.sync.primary == "youtrack_issue": ids["youtrack_issue"] = data["idReadable"]
        if document.sync.primary == "github_issue": ids["github_issue"] = f"{document.platform_ids['github_issue'].rsplit('#', 1)[0]}#{data['number']}"
        if document.sync.primary == "github_pull_request": ids["github_pull_request"] = f"{data['base']['repo']['full_name']}#{data['number']}"
        metadata["id"] = ids
        metadata = drop_empty(metadata)
        if document.sync.primary in ("github_issue", "github_pull_request", "gitee_issue", "gitee_pull_request"):
            key = document.sync.primary
            repository = data.get("repository", {}).get("full_name") or document.platform_ids[key].rsplit("#", 1)[0]
            platform = {"title": data.get("title"), "repository": repository, "state": data.get("state")}
            if data.get("user", {}).get("login"): platform["author"] = data["user"]["login"]
            if data.get("labels"): platform["labels"] = [label.get("name") for label in data["labels"]]
            if data.get("assignees"): platform["assignees"] = [user.get("login") for user in data["assignees"]]
            if data.get("milestone"): platform["milestone"] = data["milestone"].get("title")
            relationships = {}
            if key in ("github_issue", "gitee_issue"):
                parent = data.get("_sync_parent_issue") or {}
                if parent.get("number"): relationships["parent_issue"] = [f"{repository}#{parent['number']}"]
                children = [f"{repository}#{item['number']}" for item in data.get("_sync_sub_issues", []) if item.get("number")]
                if children: relationships["sub_issues"] = children
                connected_prs = [f"{repository}#{item['number']}" for item in data.get("_sync_connected_prs", []) if item.get("number")]
                if connected_prs: relationships["pull_requests"] = connected_prs
            if key in ("github_pull_request", "gitee_pull_request"):
                platform.update({"base_branch": data.get("base", {}).get("ref"), "head_branch": data.get("head", {}).get("ref"), "draft": data.get("draft", False), "merged": data.get("merged", False)})
                development = data.get("_sync_development", {})
                platform["development"] = {"commits": [item.get("sha") for item in development.get("commits", []) if item.get("sha")], "reviewers": [item.get("login") for item in development.get("reviewers", {}).get("users", []) if item.get("login")], "checks": [{"name": item.get("name"), "status": item.get("status"), "conclusion": item.get("conclusion")} for item in development.get("checks", [])], "deployments": [{"environment": item.get("environment"), "sha": item.get("sha"), "url": item.get("environment_url") or item.get("target_url")} for item in development.get("deployments", [])]}
            if relationships: platform["relationships"] = relationships
            metadata.setdefault("platform", {})[key] = drop_empty(platform)
        elif document.sync.primary == "youtrack_issue":
            issue_platform = {}
            if data.get("summary"): issue_platform["title"] = data["summary"]
            fields = {}
            project = data.get("project") or {}
            project_name = project.get("shortName") or project.get("name")
            if project_name: fields["project"] = project_name
            for api_key, yaml_key in (("reporter", "reporter"), ("updater", "updater")):
                person = data.get(api_key) or {}
                value = person.get("login") or person.get("fullName")
                if value: fields[yaml_key] = value
            tags = [tag.get("name") for tag in (data.get("tags") or []) if tag.get("name")]
            if tags: fields["tags"] = tags
            aliases = {
                "state": "status", "priority": "priority", "type": "type", "assignee": "assignee",
                "subsystem": "subsystem", "fix versions": "fix_versions", "affected versions": "affected_versions",
                "fixed in build": "fix_in_build", "estimate": "estimate", "actual time": "actual_time",
                "预估": "estimate", "实际用时": "actual_time", "状态": "status", "优先级": "priority",
                "类型": "type", "被指派者": "assignee", "子系统": "subsystem",
                "修复版本": "fix_versions", "受影响的版本": "affected_versions", "在以下内部版本中修复": "fix_in_build",
                "dashboard": "dashboard", "parent for": "parent_issue"
            }
            for field in data.get("customFields", []):
                name = field.get("name", "").lower()
                key = aliases.get(name)
                if not key: continue
                value = field.get("value")
                values = value if isinstance(value, list) else [value]
                clean = []
                for item in values:
                    if isinstance(item, dict): item = item.get("name") or item.get("login") or item.get("fullName") or item.get("presentation")
                    if item not in (None, ""): clean.append(item)
                if clean: fields[key] = clean if key in ("fix_versions", "affected_versions") else clean[0]
            links = {"blocks": [], "depends_on": [], "parent_issue": [], "child_issues": []}
            for link in data.get("links", []):
                relation = (link.get("linkType") or {})
                for issue in link.get("issues", []):
                    ident = issue.get("idReadable")
                    if not ident: continue
                    if relation.get("sourceToTarget") == "is required for" and link.get("direction") == "OUTWARD": links["blocks"].append(ident)
                    elif relation.get("targetToSource") == "depends on" and link.get("direction") == "INWARD": links["depends_on"].append(ident)
                    elif relation.get("targetToSource") == "subtask of" and link.get("direction") == "INWARD": links["parent_issue"].append(ident)
                    elif relation.get("sourceToTarget") == "parent for" and link.get("direction") == "OUTWARD": links["child_issues"].append(ident)
            issue_platform.update(fields)
            for key, values in links.items():
                if values: issue_platform.setdefault("relations", {})[key] = values
            if issue_platform: metadata.setdefault("platform", {})["youtrack_issue"] = issue_platform
        elif document.sync.primary == "youtrack_article":
            article_platform = {}
            if data.get("summary"): article_platform["title"] = data["summary"]
            project = data.get("project") or {}
            project_name = project.get("shortName") or project.get("name")
            if project_name: article_platform["project"] = project_name
            relations = {}
            parent = data.get("parentArticle") or {}
            parent_id = parent.get("idReadable") or parent.get("id")
            if parent_id: relations["parent_article"] = [parent_id]
            children = data.get("childArticles") or []
            child_ids = [item.get("idReadable") or item.get("id") for item in children if item.get("idReadable") or item.get("id")]
            if child_ids: relations["child_articles"] = child_ids
            if relations: article_platform["relations"] = relations
            if article_platform: metadata.setdefault("platform", {})["youtrack_article"] = article_platform
        document.metadata = metadata
        file.write_text(render_document(document, body), encoding="utf-8", newline="")
        return SyncResult(SyncStatus.SUCCESS, "remote_to_local", document.general_id)

    def upload(self, file: Path, target: str | None = None) -> None:
        document = parse_file(file)
        self._require_sync_metadata(document, "upload")
        if not target or len(target.split("/")) < 3:
            raise ValueError("upload 必须指定 --target provider/type/project，例如 youtrack/issue/DEMO")
        provider, object_type, project = target.split("/", 2)
        if provider == "github" and object_type in ("issue", "pull-request") and project:
            target_key = "github_issue" if object_type == "issue" else "github_pull_request"
            if document.platform_ids.get(target_key): raise ValueError(f"upload 目标 {target_key} 已有 ID")
            response = self.providers["github"].create(document, "issue" if object_type == "issue" else "pull_request", project)
            document.ids[target_key] = response["id"]
            document.metadata["id"] = document.ids
            document.metadata.setdefault("platform", {}).setdefault(target_key, {})["repository"] = project
            relations = document.metadata.get("platform", {}).get(target_key, {}).get("relationships", {})
            parents = relations.get("parent_issue", []) if isinstance(relations, dict) else []
            if parents:
                self.providers["github"].set_parent_issue(response["id"], parents[0])
            linked_prs = relations.get("pull_requests", []) if isinstance(relations, dict) else []
            if linked_prs:
                print("WARNING: GitHub Development PR links cannot be created through the public API; pull_requests was kept locally only.", file=sys.stderr)
            document.path.write_text(render_document(document), encoding="utf-8", newline="")
            return {"status": "SUCCESS", "provider": target_key, "id": response["id"], "local_file": str(document.path)}
        if provider == "gitee" and object_type in ("issue", "pull-request") and project:
            target_key = "gitee_issue" if object_type == "issue" else "gitee_pull_request"
            if document.platform_ids.get(target_key):
                raise ValueError(f"upload target {target_key} already has ID")
            response = self.providers["gitee"].create(document, "issue" if object_type == "issue" else "pull_request", project)
            document.ids[target_key] = response["id"]
            document.metadata["id"] = document.ids
            document.metadata.setdefault("platform", {}).setdefault(target_key, {})["repository"] = project
            document.path.write_text(render_document(document), encoding="utf-8", newline="")
            return {"status": "SUCCESS", "provider": target_key, "id": response["id"], "local_file": str(document.path)}
        if provider != "youtrack" or object_type not in ("issue", "article") or not project:
            raise ValueError("当前支持 youtrack/issue/PROJECT、youtrack/article/PROJECT、github/issue/OWNER/REPO")
        target_key = f"youtrack_{object_type}"
        if document.platform_ids.get(target_key):
            raise ValueError(f"upload 目标 {target_key} 已有 ID，创建被拒绝；请使用 sync-to-remote")
        response = self.providers.get("youtrack").create(document, object_type, project)
        remote_id = response.get("idReadable") or response.get("id")
        if not remote_id:
            raise RuntimeError("远端创建成功但未返回可绑定的 Article/Issue ID")
        document.ids[target_key] = remote_id
        document.metadata["id"] = document.ids
        target_metadata = document.metadata.setdefault("platform", {}).setdefault(target_key, {})
        target_metadata["project"] = project
        if response.get("summary"):
            target_metadata["title"] = response["summary"]
        if object_type == "issue":
            relations = target_metadata.get("relations", {})
            for relation in ("blocks", "depends_on", "parent_issue"):
                values = relations.get(relation, []) if isinstance(relations, dict) else []
                for related_id in values if isinstance(values, list) else [values]:
                    self.providers["youtrack"].link_issue(remote_id, relation, related_id)
        if object_type == "article":
            relations = target_metadata.get("relations", {})
            parents = relations.get("parent_article", []) if isinstance(relations, dict) else []
            if parents:
                self.providers["youtrack"].set_parent_article(remote_id, parents[0])
        document.path.write_text(render_document(document), encoding="utf-8", newline="")
        return {"status": "SUCCESS", "provider": target_key, "id": remote_id, "local_file": str(document.path)}

    def sync_to_remote(self, file: Path, joint: bool = False):
        # Remote IDs are authoritative; the local file is only a backup/update payload.
        document = parse_file(file)
        self._require_sync_metadata(document, "sync-to-remote")
        # The first ID is the authority for conflict resolution, but every
        # existing platform ID must be updated so cross-platform sync works.
        updated = []
        for key in document.sync.order:
            if key == "general" or not document.platform_ids.get(key):
                continue
            provider_name = "github" if key.startswith("github_") else ("gitee" if key.startswith("gitee_") else "youtrack")
            provider = self.providers.get(provider_name)
            if not provider:
                raise ValueError(f"provider not configured: {provider_name}")
            self.logger.info("sync_provider primary=%s current=%s joint=%s", document.sync.primary, key, joint)
            provider.update(document, document.body, joint=joint)
            updated.append(key)
        return {"status": "SUCCESS", "operation": "sync-to-remote", "updated": updated, "ids": document.platform_ids}

    @staticmethod
    def _require_sync_metadata(document, operation: str) -> None:
        if not document.metadata or "doc_type" not in document.metadata:
            raise ValueError(f"{operation} requires YAML front matter with doc_type: markdown")
        if document.metadata.get("doc_type") != "markdown":
            raise ValueError(f"{operation} only supports doc_type: markdown")
        if not document.platform_ids:
            raise ValueError(f"{operation} requires at least one platform ID in YAML id")

    def _not_implemented(self, direction: str, file: Path) -> SyncResult:
        document = parse_file(file)
        result = SyncResult(SyncStatus.NOT_FOUND, direction, document.general_id)
        result.add(status="NOT_IMPLEMENTED", reason="provider adapter pending")
        return result
