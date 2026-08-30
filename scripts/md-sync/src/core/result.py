from dataclasses import dataclass, field
from enum import Enum
class SyncStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_METADATA = "INVALID_METADATA"
@dataclass
class SyncResult:
    status: SyncStatus
    direction: str
    general_id: str | None
    details: list[dict] = field(default_factory=list)
    def add(self, **detail): self.details.append(detail)
