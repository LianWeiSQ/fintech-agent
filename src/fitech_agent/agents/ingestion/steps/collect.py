from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ....adapters import SourceAdapter
from ....models import NewsWindow, RawNewsItem
from ....utils import utc_now_iso


def _item_sort_key(item: RawNewsItem) -> tuple[float, float, str]:
    priority = float(item.metadata.get("source_priority", 0) or 0)
    trust_score = float(item.metadata.get("source_trust_score", 0.0) or 0.0)
    return (priority, trust_score, item.published_at)


class NewsCollectionAgent:
    def __init__(self, adapters: list[SourceAdapter]) -> None:
        self.adapters = adapters

    def run(self, window: NewsWindow) -> tuple[list[RawNewsItem], list[str]]:
        if not self.adapters:
            return [], ["no_sources_configured"]

        collected_at = utc_now_iso()
        items: list[RawNewsItem] = []
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=min(6, len(self.adapters))) as executor:
            future_map = {
                executor.submit(adapter.fetch, window, collected_at): adapter.definition.name
                for adapter in self.adapters
            }
            for future in as_completed(future_map):
                source_name = future_map[future]
                try:
                    items.extend(future.result())
                except Exception as exc:
                    errors.append(f"source_failed:{source_name}:{exc}")

        return sorted(items, key=_item_sort_key, reverse=True), errors
