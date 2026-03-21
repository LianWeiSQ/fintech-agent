from __future__ import annotations

from ...models import CollectedNewsBatch, EventIntelligenceBundle
from ..base import AgentRuntimeContext, BaseResearchAgent
from ..registry import get_agent_descriptor
from .runtime import EventIntelligenceRuntime
from .steps.credibility import CredibilityAgent
from .steps.extract import EventExtractionAgent
from .steps.normalize import NormalizationAgent
from .steps.translate_or_summarize import translation_summary


class EventIntelligenceAgent(BaseResearchAgent[CollectedNewsBatch, EventIntelligenceBundle]):
    descriptor = get_agent_descriptor("event_intelligence")

    def __init__(self, report_language: str) -> None:
        self.report_language = report_language

    def execute(
        self,
        context: AgentRuntimeContext,
        payload: CollectedNewsBatch,
    ) -> EventIntelligenceBundle:
        runtime = EventIntelligenceRuntime(self.descriptor, context.skill)
        normalizer = NormalizationAgent()
        clusters = normalizer.run(payload.raw_items)
        context.storage.record_stage(
            context.run_id,
            stage="event_intelligence",
            agent_id="event_intelligence",
            substage="normalize",
            entity_type="news_cluster",
            payloads=clusters,
            entity_ids=[cluster.id for cluster in clusters],
        )

        extractor = EventExtractionAgent(context.llm_client, self.report_language, runtime=runtime)
        events = extractor.run(clusters)
        context.storage.record_stage(
            context.run_id,
            stage="event_intelligence",
            agent_id="event_intelligence",
            substage="extract",
            entity_type="canonical_news_event",
            payloads=events,
            entity_ids=[event.id for event in events],
        )

        context.storage.record_stage(
            context.run_id,
            stage="event_intelligence",
            agent_id="event_intelligence",
            substage="translate_or_summarize",
            entity_type="translation_summary",
            payloads=[translation_summary(clusters, self.report_language)],
            entity_ids=["translate_or_summarize"],
        )

        scorer = CredibilityAgent()
        scores = scorer.run(events)
        context.storage.record_stage(
            context.run_id,
            stage="event_intelligence",
            agent_id="event_intelligence",
            substage="score_credibility",
            entity_type="credibility_score",
            payloads=scores,
            entity_ids=[score.event_id for score in scores],
        )

        return EventIntelligenceBundle(
            collected=payload,
            clusters=clusters,
            events=events,
            credibility_scores=scores,
        )
