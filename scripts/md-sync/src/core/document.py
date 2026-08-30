from dataclasses import dataclass, field
from pathlib import Path
PLATFORM_IDS = ("github_issue", "github_pull_request", "gitee_issue", "gitee_pull_request", "youtrack_issue", "youtrack_article")
@dataclass(frozen=True)
class SyncPolicy:
    primary: str | None = None
    order: tuple[str, ...] = ()
@dataclass
class MarkdownDocument:
    path: Path
    metadata: dict
    body: str
    ids: dict[str, str] = field(default_factory=dict)
    sync: SyncPolicy = field(default_factory=SyncPolicy)
    @property
    def general_id(self): return self.ids.get("general")
    @property
    def platform_ids(self): return {k: v for k, v in self.ids.items() if k in PLATFORM_IDS and v}
