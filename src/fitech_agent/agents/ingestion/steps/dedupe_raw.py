from __future__ import annotations

from ....models import RawNewsItem


def dedupe_raw_items(items: list[RawNewsItem]) -> list[RawNewsItem]:
    unique: dict[str, RawNewsItem] = {}
    for item in sorted(items, key=lambda entry: entry.published_at, reverse=True):
        unique[item.url or item.id] = item
    return list(unique.values())
