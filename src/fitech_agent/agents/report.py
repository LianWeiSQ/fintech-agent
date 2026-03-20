from __future__ import annotations

from ..models import CanonicalNewsEvent, DailyMarketBrief, IntegratedView, MarketImpactAssessment
from ..utils import stable_id, utc_now_iso


class ReportGenerationAgent:
    def run(self, run_id: int, scheduled_for: str, events: list[CanonicalNewsEvent], assessments: list[MarketImpactAssessment], integrated_view: IntegratedView, degraded_reasons: list[str]) -> DailyMarketBrief:
        ready = [item for item in assessments if item.status == "ready"]
        watch_only = [item for item in assessments if item.status != "ready"]
        overnight_focus = [event.title for event in events[:5]]
        core_events = [event.summary for event in events[:5]]
        watchlist = list(dict.fromkeys(integrated_view.watchlist + [item.strategy_view for item in watch_only]))[:12]
        evidence_appendix = []
        for item in ready[:8]:
            evidence_titles = " / ".join(ref.source for ref in item.key_evidence[:2])
            evidence_appendix.append(f"{item.domain} | {item.direction} | {item.strategy_view} | {evidence_titles}")
        report_id = stable_id(str(run_id), scheduled_for, size=16)
        return DailyMarketBrief(
            report_id=report_id,
            run_id=run_id,
            scheduled_for=scheduled_for,
            generated_at=utc_now_iso(),
            overnight_focus=overnight_focus,
            core_events=core_events,
            cross_asset_themes=integrated_view.cross_asset_themes,
            equity_view=integrated_view.equity_view or ["暂无高置信度A股主线。"],
            commodities_view=integrated_view.commodities_view or ["暂无高置信度商品主线。"],
            precious_metals_view=integrated_view.precious_metals_view or ["暂无高置信度贵金属主线。"],
            crude_oil_view=integrated_view.crude_oil_view or ["暂无高置信度原油主线。"],
            risk_scenarios=integrated_view.risk_scenarios,
            watchlist=watchlist,
            evidence_appendix=evidence_appendix or ["暂无可发布级别证据，请人工复核。"],
            markdown_body="",
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
        )
