from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..config import SourceDefinition
from ..models import NewsWindow, RawNewsItem


class SourceAdapter(ABC):
    def __init__(self, definition: SourceDefinition) -> None:
        self.definition = definition

    @abstractmethod
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        raise NotImplementedError


def build_source_metadata(
    definition: SourceDefinition,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = dict(definition.metadata)
    if extra:
        metadata.update(extra)
    metadata.update(
        {
            "source_confidence_level": definition.confidence_level,
            "source_confidence_category": definition.confidence_category,
            "source_trust_score": definition.trust_score,
            "source_priority": definition.priority,
            "source_tier": definition.tier,
        }
    )
    return metadata


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
