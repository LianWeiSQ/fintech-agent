from __future__ import annotations

from ...models import EventIntelligenceBundle, MarketReasoningBundle
from ..base import AgentRuntimeContext, BaseResearchAgent
from ..registry import get_agent_descriptor
from .runtime import MarketReasoningRuntime
from .steps.domain_analysis import DomainAnalysisAgent
from .steps.mapping import AssetMappingAgent
from .steps.scope_filter import filter_by_scope
from .steps.strategy_integration import StrategyIntegrationAgent


class MarketReasoningAgent(BaseResearchAgent[EventIntelligenceBundle, MarketReasoningBundle]):
    descriptor = get_agent_descriptor("market_reasoning")

    def execute(
        self,
        context: AgentRuntimeContext,
        payload: EventIntelligenceBundle,
    ) -> MarketReasoningBundle:
        _runtime = MarketReasoningRuntime(self.descriptor, context.skill)
        mapper = AssetMappingAgent()
        mappings = mapper.run(payload.events)
        context.storage.record_stage(
            context.run_id,
            stage="market_reasoning",
            agent_id="market_reasoning",
            substage="map_assets",
            entity_type="event_asset_map",
            payloads=mappings,
            entity_ids=[mapping.event_id for mapping in mappings],
        )

        filtered_events, filtered_mappings = filter_by_scope(payload.events, mappings, context.scopes)
        allowed_event_ids = {event.id for event in filtered_events}
        filtered_scores = [
            score for score in payload.credibility_scores if score.event_id in allowed_event_ids
        ]
        context.storage.record_stage(
            context.run_id,
            stage="market_reasoning",
            agent_id="market_reasoning",
            substage="filter_scope",
            entity_type="scope_filter_summary",
            payloads=[
                {
                    "selected_scopes": list(context.scopes),
                    "events_before": len(payload.events),
                    "events_after": len(filtered_events),
                    "mappings_after": len(filtered_mappings),
                }
            ],
            entity_ids=["filter_scope"],
        )

        analyzer = DomainAnalysisAgent()
        assessments = analyzer.run(filtered_events, filtered_scores, filtered_mappings)
        context.storage.record_stage(
            context.run_id,
            stage="market_reasoning",
            agent_id="market_reasoning",
            substage="analyze_domains",
            entity_type="market_impact_assessment",
            payloads=assessments,
            entity_ids=[assessment.id for assessment in assessments],
        )

        strategist = StrategyIntegrationAgent()
        integrated_view = strategist.run(assessments)
        context.storage.record_stage(
            context.run_id,
            stage="market_reasoning",
            agent_id="market_reasoning",
            substage="integrate_strategy",
            entity_type="integrated_view",
            payloads=[integrated_view],
            entity_ids=["integrated_view"],
        )

        return MarketReasoningBundle(
            intelligence=EventIntelligenceBundle(
                collected=payload.collected,
                clusters=list(payload.clusters),
                events=filtered_events,
                credibility_scores=filtered_scores,
            ),
            scopes=list(context.scopes),
            mappings=filtered_mappings,
            assessments=assessments,
            integrated_view=integrated_view,
        )
