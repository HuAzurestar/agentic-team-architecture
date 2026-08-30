from abc import ABC, abstractmethod
from src.core.document import MarkdownDocument
class RemoteProvider(ABC):
    name: str
    @abstractmethod
    def fetch(self, document: MarkdownDocument) -> str: ...
    @abstractmethod
    def update(self, document: MarkdownDocument, body: str) -> None: ...
