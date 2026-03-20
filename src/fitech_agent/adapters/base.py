from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import SourceDefinition
from ..models import NewsWindow, RawNewsItem


class SourceAdapter(ABC):
    def __init__(self, definition: SourceDefinition) -> None:
        self.definition = definition

    @abstractmethod
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        raise NotImplementedError


def build_adapter(definition: SourceDefinition) -> SourceAdapter:
    if definition.kind == "file":
        from .file import FileSourceAdapter

        return FileSourceAdapter(definition)
    if definition.kind == "rss":
        from .rss import RSSSourceAdapter

        return RSSSourceAdapter(definition)
    if definition.kind == "mock":
        from .mock import MockSourceAdapter

        return MockSourceAdapter(definition)
    raise ValueError(f"Unsupported source kind: {definition.kind}")

