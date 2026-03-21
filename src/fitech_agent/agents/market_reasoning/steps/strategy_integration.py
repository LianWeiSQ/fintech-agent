from __future__ import annotations

from collections import defaultdict

from ....models import IntegratedView, MarketImpactAssessment


class StrategyIntegrationAgent:
    def run(self, assessments: list[MarketImpactAssessment]) -> IntegratedView:
        by_domain: dict[str, list[MarketImpactAssessment]] = defaultdict(list)
        for assessment in sorted(assessments, key=lambda item: item.confidence, reverse=True):
            by_domain[assessment.domain].append(assessment)

        def top_views(domain: str, limit: int = 3) -> list[str]:
            return [item.strategy_view for item in by_domain.get(domain, [])[:limit]]

        cross_asset_themes = [item.strategy_view for item in sorted(assessments, key=lambda item: item.confidence, reverse=True)[:4]]
        risk_scenarios = list(dict.fromkeys(risk for item in assessments for risk in item.downside_risks))[:6]
        watchlist = list(dict.fromkeys(point for item in assessments for point in item.watchlist))[:10]
        return IntegratedView(
            cross_asset_themes=cross_asset_themes,
            equity_view=top_views("equities"),
            commodities_view=top_views("commodities"),
            precious_metals_view=top_views("precious_metals"),
            crude_oil_view=top_views("energy"),
            risk_scenarios=risk_scenarios,
            watchlist=watchlist,
        )

