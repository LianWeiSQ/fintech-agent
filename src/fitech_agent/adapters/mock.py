from __future__ import annotations

from ..models import NewsWindow, RawNewsItem
from ..utils import stable_id
from .base import SourceAdapter


class MockSourceAdapter(SourceAdapter):
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        if self.definition.endpoint == "error":
            raise RuntimeError(f"Mock source {self.definition.name} forced failure")

        sample_title = {
            "fomc_hawkish": "Fed signals rates may stay restrictive for longer",
            "china_stimulus": "China unveils fresh measures to stabilize growth",
        }.get(self.definition.endpoint, "Mock macro news headline")
        return [
            RawNewsItem(
                id=stable_id(self.definition.name, sample_title, window.end, size=16),
                source=self.definition.name,
                source_type="mock",
                source_tier=self.definition.tier,
                language=self.definition.language,
                title=sample_title,
                summary=sample_title,
                url=f"mock://{self.definition.endpoint}",
                published_at=window.end,
                collected_at=collected_at,
                tags=list(self.definition.tags),
                metadata={"mock": True},
            )
        ]

