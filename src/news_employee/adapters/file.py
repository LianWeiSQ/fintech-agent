from __future__ import annotations

import json
from pathlib import Path

from ..models import NewsWindow, RawNewsItem
from ..utils import parse_iso_datetime, stable_id
from .base import SourceAdapter


class FileSourceAdapter(SourceAdapter):
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        source_path = Path(self.definition.endpoint)
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        items = []
        window_start = parse_iso_datetime(window.start)
        window_end = parse_iso_datetime(window.end)
        for item in payload:
            published_at = item["published_at"]
            published_dt = parse_iso_datetime(published_at)
            if (
                published_dt is not None
                and window_start is not None
                and window_end is not None
                and not (window_start <= published_dt <= window_end)
            ):
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
