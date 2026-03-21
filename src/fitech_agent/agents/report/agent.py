from __future__ import annotations

from pathlib import Path

from ...models import AuditBundle, ReportBundle
from ...reporting import render_markdown
from ..base import AgentRuntimeContext, BaseResearchAgent
from ..registry import get_agent_descriptor
from .runtime import ReportRuntime
from .steps.compose import ReportGenerationAgent
from .steps.persist import persist_report
from .steps.render import render_report_artifacts


class ReportAgent(BaseResearchAgent[AuditBundle, ReportBundle]):
    descriptor = get_agent_descriptor("report")

    def execute(
        self,
        context: AgentRuntimeContext,
        payload: AuditBundle,
    ) -> ReportBundle:
        _runtime = ReportRuntime(self.descriptor, context.skill)
        reporter = ReportGenerationAgent()
        reasoning = payload.reasoning
        intelligence = reasoning.intelligence
        collected = intelligence.collected
        report = reporter.run(
            run_id=context.run_id,
            triggered_at=context.triggered_at,
            mode=context.mode,  # type: ignore[arg-type]
            window=context.window,
            scopes=list(context.scopes),
            sources=list(collected.sources),
            events=intelligence.events,
            assessments=payload.assessments,
            integrated_view=reasoning.integrated_view,
            degraded_reasons=payload.degraded_reasons,
        )
        context.storage.record_stage(
            context.run_id,
            stage="report",
            agent_id="report",
            substage="compose_brief",
            entity_type="research_brief",
            payloads=[report],
            entity_ids=[report.report_id],
        )

        markdown_path, pdf_path, render_warnings = render_report_artifacts(report, context.config.report_dir)
        context.storage.record_stage(
            context.run_id,
            stage="report",
            agent_id="report",
            substage="render_markdown",
            entity_type="report_artifact",
            payloads=[{"markdown_path": markdown_path}],
            entity_ids=["render_markdown"],
        )
        context.storage.record_stage(
            context.run_id,
            stage="report",
            agent_id="report",
            substage="render_pdf",
            entity_type="report_artifact",
            payloads=[{"pdf_path": pdf_path, "warnings": render_warnings}],
            entity_ids=["render_pdf"],
        )

        if render_warnings:
            report.degraded = True
            report.degraded_reasons = list(dict.fromkeys(report.degraded_reasons + render_warnings))
            report.markdown_body = render_markdown(report)
            Path(markdown_path).write_text(report.markdown_body, encoding="utf-8")

        persist_report(context, report, markdown_path, pdf_path)
        context.storage.record_stage(
            context.run_id,
            stage="report",
            agent_id="report",
            substage="persist_report",
            entity_type="report_artifact",
            payloads=[{"markdown_path": markdown_path, "pdf_path": pdf_path}],
            entity_ids=["persist_report"],
        )
        return ReportBundle(
            audit=payload,
            report=report,
            markdown_path=markdown_path,
            pdf_path=pdf_path,
        )
