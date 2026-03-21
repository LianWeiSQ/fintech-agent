from __future__ import annotations

from ....models import NewsCluster


def needs_translation(report_language: str, source_language: str) -> bool:
    return report_language.startswith("zh") and not source_language.startswith("zh")


def translation_summary(clusters: list[NewsCluster], report_language: str) -> dict[str, int | str]:
    count = 0
    for cluster in clusters:
        if any(needs_translation(report_language, language) for language in cluster.source_languages):
            count += 1
    return {
        "report_language": report_language,
        "clusters_considered": len(clusters),
        "translation_candidates": count,
    }
