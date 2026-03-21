from __future__ import annotations

from ....config import SourceDefinition


def select_sources(
    enabled_sources: list[SourceDefinition],
    requested_sources: list[str] | None,
) -> list[SourceDefinition]:
    if not requested_sources:
        return list(enabled_sources)

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

    return [
        source
        for source in enabled_sources
        if source.name.strip().lower() in requested_lookup
    ]
