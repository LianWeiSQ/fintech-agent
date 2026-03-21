from __future__ import annotations

from ...base import AgentRuntimeContext
from ....models import ResearchBrief


def persist_report(
    context: AgentRuntimeContext,
    report: ResearchBrief,
    markdown_path: str,
    pdf_path: str | None,
) -> None:
    context.storage.save_report(context.run_id, report, markdown_path, pdf_path)
    context.storage.finalize_run(
        context.run_id,
        status="completed",
        degraded=report.degraded,
        degraded_reasons=report.degraded_reasons,
    )
