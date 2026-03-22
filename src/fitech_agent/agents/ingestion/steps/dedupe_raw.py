from __future__ import annotations

from ....models import RawNewsItem


def _item_sort_key(item: RawNewsItem) -> tuple[float, float, str]:
    priority = float(item.metadata.get("source_priority", 0) or 0)
    trust_score = float(item.metadata.get("source_trust_score", 0.0) or 0.0)
    return (priority, trust_score, item.published_at)


def dedupe_raw_items(items: list[RawNewsItem]) -> list[RawNewsItem]:
    unique: dict[str, RawNewsItem] = {}
    for item in sorted(items, key=_item_sort_key, reverse=True):
        unique[item.url or item.id] = item
    return list(unique.values())
