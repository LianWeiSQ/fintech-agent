from __future__ import annotations

from ....models import ResearchBrief
from ....reporting import render_markdown, save_report_artifacts


def render_report_artifacts(
    report: ResearchBrief,
    report_dir: str,
) -> tuple[str, str | None, list[str]]:
    report.markdown_body = render_markdown(report)
    return save_report_artifacts(report, report_dir)
