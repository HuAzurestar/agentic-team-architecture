"""Synchronization orchestration. Providers are intentionally replaceable."""
from pathlib import Path

from src.document import parse_file, render_document
from src.document.parser import parse_text
from src.core.result import SyncResult, SyncStatus
from src.controller.metadata import drop_empty


class SyncController:
    def __init__(self, config: dict):
        self.config = config
        self.providers = {}
        yt = config.get("providers", {}).get("youtrack", {})
        if yt.get("enabled") and yt.get("token"):
            from src.providers.youtrack import YouTrackProvider
            self.providers["youtrack"] = YouTrackProvider(yt)

    def status(self) -> None:
        print(f"mode: {self.config.get('mode', 'remote_authoritative')}")
        print("providers: " + ", ".join(self.providers) if self.providers else "providers: none")

    def download(self, file: Path, remote: str | None = None) -> None:
        if not file.exists():
            if not remote or ":" not in remote:
                raise FileNotFoundError(f"本地文件不存在，请使用 --remote provider:id: {file}")
            provider_name, remote_id = remote.split(":", 1)
            key = provider_name if provider_name in ("youtrack_article", "youtrack_issue") else f"{provider_name}_article"
            document = parse_text(f'---\ndoc_type: markdown\nid:\n  {key}: "{remote_id}"\nsync:\n  primary: {key}\n  order: [{key}]\n---\n', file)
        else:
            document = parse_file(file)
        provider = self.providers.get("youtrack")
        if not provider: return self._not_implemented("remote_to_local", file)
        data, body = provider.fetch(document)
        metadata = dict(document.metadata)
        ids = dict(metadata.get("id", {}))
        if document.sync.primary == "youtrack_article": ids["youtrack_article"] = data.get("idReadable", data["id"])
        if document.sync.primary == "youtrack_issue": ids["youtrack_issue"] = data["idReadable"]
        metadata["id"] = ids
        metadata = drop_empty(metadata)
        if document.sync.primary == "youtrack_issue":
            issue_platform = {}
            if data.get("summary"): issue_platform["title"] = data["summary"]
            fields = {}
            project = data.get("project") or {}
            project_name = project.get("shortName") or project.get("name")
            if project_name: fields["project"] = project_name
            aliases = {
                "state": "status", "priority": "priority", "type": "type", "assignee": "assignee",
                "subsystem": "subsystem", "fix versions": "fix_versions", "affected versions": "affected_versions",
                "fixed in build": "fix_in_build", "estimate": "estimate", "actual time": "actual_time",
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
            links = {"blocks": [], "depends_on": [], "parent": []}
            for link in data.get("links", []):
                relation = (link.get("linkType") or {})
                for issue in link.get("issues", []):
                    ident = issue.get("idReadable")
                    if not ident: continue
                    if relation.get("sourceToTarget") == "is required for" and link.get("direction") == "OUTWARD": links["blocks"].append(ident)
                    elif relation.get("targetToSource") == "depends on" and link.get("direction") == "INWARD": links["depends_on"].append(ident)
                    elif relation.get("targetToSource") == "subtask of" and link.get("direction") == "INWARD": links["parent"].append(ident)
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
            if article_platform: metadata.setdefault("platform", {})["youtrack_article"] = article_platform
        metadata.setdefault("sync", {"primary": document.sync.primary, "order": list(document.sync.order)})
        document.metadata = metadata
        file.write_text(render_document(document, body), encoding="utf-8", newline="")
        return SyncResult(SyncStatus.SUCCESS, "remote_to_local", document.general_id)

    def upload(self, file: Path, target: str | None = None) -> None:
        document = parse_file(file)
        if not target or len(target.split("/")) < 3:
            raise ValueError("upload 必须指定 --target provider/type/project，例如 youtrack/issue/DEMO")
        provider, object_type, project = target.split("/", 2)
        if provider != "youtrack" or object_type not in ("issue", "article") or not project:
            raise ValueError("当前只支持 youtrack/issue/PROJECT 或 youtrack/article/PROJECT")
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
        document.path.write_text(render_document(document), encoding="utf-8", newline="")
        return {"status": "SUCCESS", "provider": target_key, "id": remote_id, "local_file": str(document.path)}
        result = SyncResult(SyncStatus.SUCCESS, "local_to_remote", document.general_id)
        if not document.platform_ids:
            result.status = SyncStatus.NOT_FOUND
            result.add(status="FAILED", reason="no_platform_id")
            return result
        provider = self.providers.get("youtrack")
        if not provider:
            result.status = SyncStatus.NOT_FOUND
            result.add(status="FAILED", reason="youtrack_not_configured")
            return result
        try:
            provider.update(document, document.body)
            for key in document.platform_ids:
                if key.startswith("youtrack_"):
                    result.add(provider=key, id=document.platform_ids[key], status="SUCCESS")
        except Exception as exc:
            result.status = SyncStatus.PARTIAL_SUCCESS
            result.add(provider="youtrack", status="FAILED", error=str(exc))
        return result

    def _not_implemented(self, direction: str, file: Path) -> SyncResult:
        document = parse_file(file)
        result = SyncResult(SyncStatus.NOT_FOUND, direction, document.general_id)
        result.add(status="NOT_IMPLEMENTED", reason="provider adapter pending")
        return result
