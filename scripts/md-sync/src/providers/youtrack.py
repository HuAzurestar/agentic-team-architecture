import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from src.core.document import MarkdownDocument
from src.core.logging import get_logger
from .base import RemoteProvider

class YouTrackProvider(RemoteProvider):
    """YouTrack Issue and Article adapter with UTF-8 JSON payloads."""
    name = "youtrack"
    def __init__(self, config: dict):
        self.url, self.token = config["url"].rstrip("/"), config.get("token", "")
        self.logger = get_logger()

    def _get(self, path):
        self.logger.info("api_request provider=youtrack method=GET path=%s", path)
        req = Request(self.url + path, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        try:
            with urlopen(req, timeout=30) as response:
                self.logger.info("api_response provider=youtrack method=GET path=%s status=%s", path, response.status)
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            self.logger.error("api_error provider=youtrack method=GET path=%s status=%s detail=%s", path, exc.code, detail)
            raise RuntimeError(f"YouTrack API {exc.code} for GET {path}: {detail}") from exc
        except Exception as exc:
            self.logger.exception("api_error provider=youtrack method=GET path=%s error=%s", path, exc)
            raise

    def fetch(self, document: MarkdownDocument) -> tuple[dict, str]:
        key = document.sync.primary or next(iter(document.platform_ids), None)
        if key == "youtrack_article":
            remote_id = document.platform_ids[key]
            data = self._get(f"/api/articles/{remote_id}?fields=id,idReadable,summary,content,created,updated,project(name,shortName),parentArticle(id,idReadable,summary),childArticles(id,idReadable,summary)")
            return data, data.get("content", "")
        if key == "youtrack_issue":
            remote_id = document.platform_ids[key]
            data = self._get(f"/api/issues/{remote_id}?fields=idReadable,summary,description,created,updated,project(name,shortName),reporter(login,fullName),updater(login,fullName),attachments(name),tags(name),customFields(name,value(name,login,fullName,presentation)),links(direction,linkType(name,sourceToTarget,targetToSource),issues(idReadable))")
            return data, data.get("description", "")
        raise ValueError("没有可用的 YouTrack Issue/Article ID")

    def _update(self, endpoint, remote_id, payload):
        request = Request(self.url + f"/api/{endpoint}/{remote_id}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urlopen(request, timeout=30) as response:
            response.read()

    def update(self, document: MarkdownDocument, body: str, joint: bool = False) -> None:
        # Verify the remote title and body after every update so silent API
        # failures cannot be reported as a successful synchronization.
        for key, field in (("youtrack_issue", "description"), ("youtrack_article", "content")):
            remote_id = document.platform_ids.get(key)
            if not remote_id:
                continue
            platform = document.metadata.get("platform", {}).get(key, {})
            title = platform.get("title") or document.metadata.get("title") or document.metadata.get("summary") or document.path.stem
            endpoint = "issues" if key == "youtrack_issue" else "articles"
            payload = {field: body, "summary": title}
            self.logger.info("sync_payload target=%s fields=%s joint=%s", remote_id, list(payload), joint)
            if not joint:
                self.logger.info("sync_skip target=%s fields=project,customFields,relations reason=default_safe_mode", remote_id)
            self._update(endpoint, remote_id, payload)
            verify_fields = "idReadable,summary,description" if key == "youtrack_issue" else "id,summary,content"
            verified = self._get(f"/api/{endpoint}/{remote_id}?fields={verify_fields}")
            remote_body = verified.get(field, "")
            if verified.get("summary") != title or remote_body != body:
                raise RuntimeError(f"{key} 更新后回读不一致")

    def create(self, document: MarkdownDocument, object_type: str, project: str):
        platform_data = document.metadata.get("platform", {}).get(f"youtrack_{object_type}", {})
        titles = [data.get("title") for data in document.metadata.get("platform", {}).values() if isinstance(data, dict)]
        title = platform_data.get("title") or document.metadata.get("title") or next((x for x in titles if x), None) or document.path.stem
        endpoint = "issues" if object_type == "issue" else "articles"
        field = "description" if object_type == "issue" else "content"
        payload = {"summary": title, field: document.body, "project": {"shortName": project}}
        if object_type == "issue":
            custom_fields = []
            definitions = {
                "priority": ("Priority", "SingleEnumIssueCustomField", "name"),
                "type": ("Type", "SingleEnumIssueCustomField", "name"),
                "status": ("State", "StateIssueCustomField", "name"),
                "assignee": ("Assignee", "SingleUserIssueCustomField", "login"),
                "subsystem": ("Subsystem", "SingleOwnedIssueCustomField", "name"),
                "fix_versions": ("Fix versions", "MultiVersionIssueCustomField", "name"),
                "affected_versions": ("Affected versions", "MultiVersionIssueCustomField", "name"),
                "fix_in_build": ("Fixed in build", "SingleBuildIssueCustomField", "name"),
            }
            for key, (name, field_type, value_key) in definitions.items():
                value = platform_data.get(key)
                if value in (None, "", [], "?"): continue
                values = value if isinstance(value, list) else [value]
                if field_type.startswith("Multi"):
                    custom_fields.append({"name": name, "$type": field_type, "value": [{value_key: item} for item in values]})
                else:
                    custom_fields.append({"name": name, "$type": field_type, "value": {value_key: values[0]}})
            if custom_fields: payload["customFields"] = custom_fields
        return self._update_create(endpoint, payload)

    def set_parent_article(self, child_id: str, parent_id: str) -> None:
        parent = self._get(f"/api/articles/{parent_id}?fields=id")
        child = self._get(f"/api/articles/{child_id}?fields=id")
        self._update("articles", parent["id"] + "/childArticles", {"id": child["id"], "$type": "Article"})

    def link_issue(self, issue_id: str, relation: str, target_id: str) -> None:
        issue = self._get(f"/api/issues/{issue_id}?fields=id")
        target = self._get(f"/api/issues/{target_id}?fields=id")
        types = self._get("/api/issueLinkTypes?fields=id,name,sourceToTarget,targetToSource")
        wanted = "Subtask" if relation == "parent_issue" else "Depend"
        link_type = next((item for item in types if item.get("name") == wanted), None)
        if not link_type:
            raise RuntimeError(f"YouTrack link type not found: {wanted}")
        direction = "t" if relation in ("depends_on", "parent_issue") else "s"
        self._update(
            "issues",
            issue["id"] + "/links/" + link_type["id"] + direction + "/issues",
            {"id": target["id"]},
        )

    def _update_create(self, endpoint, payload):
        request = Request(self.url + f"/api/{endpoint}?fields=idReadable,id,summary", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
