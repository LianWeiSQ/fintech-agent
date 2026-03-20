from __future__ import annotations

from ..models import (
    CanonicalNewsEvent,
    IntegratedView,
    MarketImpactAssessment,
    NewsWindow,
    ResearchBrief,
    RunMode,
)
from ..utils import stable_id, utc_now_iso


def _mode_label(mode: RunMode) -> str:
    return {
        "full_report": "full-report",
        "collect_only": "collect-only",
    }[mode]


class ReportGenerationAgent:
    def run(
        self,
        *,
        run_id: int,
        triggered_at: str,
        mode: RunMode,
        window: NewsWindow,
        scopes: list[str],
        sources: list[str],
        events: list[CanonicalNewsEvent],
        assessments: list[MarketImpactAssessment],
        integrated_view: IntegratedView,
        degraded_reasons: list[str],
    ) -> ResearchBrief:
        ready = [item for item in assessments if item.status == "ready"]
        watch_only = [item for item in assessments if item.status != "ready"]
        overnight_focus = [event.title for event in events[:5]]
        core_events = [event.summary for event in events[:5]]
        watchlist = list(
            dict.fromkeys(integrated_view.watchlist + [item.strategy_view for item in watch_only])
        )[:12]
        evidence_appendix = []
        for item in ready[:8]:
            evidence_titles = " / ".join(ref.source for ref in item.key_evidence[:2])
            evidence_appendix.append(
                f"{item.domain} | {item.direction} | {item.strategy_view} | {evidence_titles}"
            )
        report_id = stable_id(str(run_id), triggered_at, size=16)
        overview = [
            f"triggered_at: {triggered_at}",
            f"window: {window.start} -> {window.end}",
            f"mode: {_mode_label(mode)}",
            f"scope: {', '.join(scopes)}",
            f"source: {', '.join(sources)}",
        ]
        return ResearchBrief(
            report_id=report_id,
            run_id=run_id,
            triggered_at=triggered_at,
            generated_at=utc_now_iso(),
            mode=mode,
            window_start=window.start,
            window_end=window.end,
            scopes=scopes,
            sources=sources,
            overview=overview,
            overnight_focus=overnight_focus or ["暂无高优先级线索。"],
            core_events=core_events or ["暂无可发布级核心事件。"],
            cross_asset_themes=integrated_view.cross_asset_themes or ["暂无明确跨资产主线。"],
            equity_view=integrated_view.equity_view or ["暂无高置信度 A 股主线。"],
            commodities_view=integrated_view.commodities_view or ["暂无高置信度商品主线。"],
            precious_metals_view=integrated_view.precious_metals_view
            or ["暂无高置信度贵金属主线。"],
            crude_oil_view=integrated_view.crude_oil_view or ["暂无高置信度原油主线。"],
            risk_scenarios=integrated_view.risk_scenarios or ["暂无新增风险情景。"],
            watchlist=watchlist or ["暂无。"],
            evidence_appendix=evidence_appendix or ["暂无可发布级别证据，请人工复核。"],
            markdown_body="",
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
        )
