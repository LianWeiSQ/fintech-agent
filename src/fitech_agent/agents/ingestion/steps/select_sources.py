from __future__ import annotations

from ....config import SourceDefinition


def _source_sort_key(source: SourceDefinition) -> tuple[int, float, str]:
    return (source.priority, source.trust_score, source.name.lower())


def select_sources(
    enabled_sources: list[SourceDefinition],
    requested_sources: list[str] | None,
) -> list[SourceDefinition]:
    if not requested_sources:
        return sorted(enabled_sources, key=_source_sort_key, reverse=True)

    requested_lookup = {
        source_name.strip().lower(): source_name.strip()
        for source_name in requested_sources
        if source_name.strip()
    }
    configured_lookup = {
        source.name.strip().lower(): source
        for source in enabled_sources
    }
    missing = [
        original
        for key, original in requested_lookup.items()
        if key not in configured_lookup
    ]
    if missing:
        raise ValueError(f"Unknown source: {', '.join(sorted(missing))}")

    selected = [
        source
        for source in enabled_sources
        if source.name.strip().lower() in requested_lookup
    ]
    return sorted(selected, key=_source_sort_key, reverse=True)
