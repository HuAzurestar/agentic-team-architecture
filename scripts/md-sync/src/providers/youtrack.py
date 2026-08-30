import json
from urllib.request import Request, urlopen
from src.core.document import MarkdownDocument
from .base import RemoteProvider

class YouTrackProvider(RemoteProvider):
    name = "youtrack"
    def __init__(self, config: dict):
        self.url, self.token = config["url"].rstrip("/"), config.get("token", "")

    def _get(self, path):
        req = Request(self.url + path, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch(self, document: MarkdownDocument) -> tuple[dict, str]:
        key = document.sync.primary or next(iter(document.platform_ids), None)
        if key == "youtrack_article":
            remote_id = document.platform_ids[key]
            data = self._get(f"/api/articles/{remote_id}?fields=id,idReadable,summary,content,created,updated")
            return data, data.get("content", "")
        if key == "youtrack_issue":
            remote_id = document.platform_ids[key]
            data = self._get(f"/api/issues/{remote_id}?fields=idReadable,summary,description,created,updated,project(name,shortName),customFields(name,value(name,login,fullName,presentation)),links(direction,linkType(name,sourceToTarget,targetToSource),issues(idReadable))")
            return data, data.get("description", "")
        raise ValueError("没有可用的 YouTrack Issue/Article ID")

    def _update(self, endpoint, remote_id, payload):
        request = Request(self.url + f"/api/{endpoint}/{remote_id}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urlopen(request, timeout=30) as response:
            response.read()

    def update(self, document: MarkdownDocument, body: str) -> None:
        title = document.metadata.get("title") or document.metadata.get("summary") or document.path.stem
        for key, field in (("youtrack_issue", "description"), ("youtrack_article", "content")):
            remote_id = document.platform_ids.get(key)
            if not remote_id:
                continue
            endpoint = "issues" if key == "youtrack_issue" else "articles"
            payload = {field: body, "summary": title}
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
        return self._update_create(endpoint, payload)

    def _update_create(self, endpoint, payload):
        request = Request(self.url + f"/api/{endpoint}?fields=idReadable,id,summary", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
