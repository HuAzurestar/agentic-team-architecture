from pathlib import Path
import yaml
from src.core.document import MarkdownDocument, PLATFORM_IDS, SyncPolicy
def parse_text(text: str, path: Path = Path("<memory>")) -> MarkdownDocument:
    metadata, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) != 3: raise ValueError("YAML Front Matter 未闭合")
        metadata, body = yaml.safe_load(parts[1]) or {}, parts[2].lstrip("\r\n")
    if metadata.get("doc_type", "markdown") != "markdown": raise ValueError("当前唯一支持 markdown")
    ids = metadata.get("id", {})
    unknown = set(ids) - {"general", *PLATFORM_IDS}
    if not isinstance(ids, dict) or unknown: raise ValueError("id 必须只包含 general 和四个平台 ID")
    sync = metadata.get("sync", {}) or {}
    if sync.get("primary") and sync["primary"] not in ids: raise ValueError("sync.primary 必须对应已有 ID")
    return MarkdownDocument(path, metadata, body, ids, SyncPolicy(sync.get("primary"), tuple(sync.get("order", ()))))
def parse_file(path: Path) -> MarkdownDocument: return parse_text(path.read_text(encoding="utf-8"), path)

def render_document(document: MarkdownDocument, body: str | None = None) -> str:
    """Render standard metadata plus Markdown body as UTF-8 text."""
    metadata = dict(document.metadata)
    metadata["doc_type"] = "markdown"
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip() + "\n---\n\n" + (document.body if body is None else body)
