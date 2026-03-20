from __future__ import annotations

import json
from pathlib import Path

from ..models import NewsWindow, RawNewsItem
from ..utils import iso_day, stable_id
from .base import SourceAdapter


class FileSourceAdapter(SourceAdapter):
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        source_path = Path(self.definition.endpoint)
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        items = []
        valid_days = {iso_day(window.start), iso_day(window.end)}
        for item in payload:
            published_at = item["published_at"]
            if iso_day(published_at) not in valid_days and published_at < window.start:
                continue
            items.append(
                RawNewsItem(
                    id=item.get(
                        "id",
                        stable_id(self.definition.name, item["title"], published_at, size=16),
                    ),
                    source=self.definition.name,
                    source_type="file",
                    source_tier=self.definition.tier,
                    language=item.get("language", self.definition.language),
                    title=item["title"],
                    summary=item.get("summary", ""),
                    url=item.get("url", ""),
                    published_at=published_at,
                    collected_at=collected_at,
                    tags=item.get("tags", list(self.definition.tags)),
                    metadata=item.get("metadata", {}),
                )
            )
        return items

