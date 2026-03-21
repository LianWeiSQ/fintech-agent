from __future__ import annotations

from ...adapters import build_adapter
from ...models import CollectedNewsBatch, ResearchRunRequest
from ..base import AgentRuntimeContext, BaseResearchAgent
from ..registry import get_agent_descriptor
from .runtime import IngestionRuntime
from .steps.collect import NewsCollectionAgent
from .steps.dedupe_raw import dedupe_raw_items
from .steps.record_raw import record_raw_batch
from .steps.select_sources import select_sources


class IngestionAgent(BaseResearchAgent[ResearchRunRequest, CollectedNewsBatch]):
    descriptor = get_agent_descriptor("ingestion")

    def execute(
        self,
        context: AgentRuntimeContext,
        payload: ResearchRunRequest,
    ) -> CollectedNewsBatch:
        _runtime = IngestionRuntime(self.descriptor, context.skill)
        enabled_sources = [source for source in context.config.sources if source.enabled]
        selected_sources = select_sources(enabled_sources, payload.sources)
        context.storage.record_stage(
            context.run_id,
            stage="ingestion",
            agent_id="ingestion",
            substage="select_sources",
            entity_type="source_definition",
            payloads=selected_sources,
            entity_ids=[source.name for source in selected_sources],
        )

        collector = NewsCollectionAgent([build_adapter(source) for source in selected_sources])
        raw_items, errors = collector.run(context.window)
        context.storage.record_stage(
            context.run_id,
            stage="ingestion",
            agent_id="ingestion",
            substage="collect",
            entity_type="raw_news_item",
            payloads=raw_items,
            entity_ids=[item.id for item in raw_items],
        )

        deduped_items = dedupe_raw_items(raw_items)
        context.storage.record_stage(
            context.run_id,
            stage="ingestion",
            agent_id="ingestion",
            substage="dedupe_raw",
            entity_type="ingestion_summary",
            payloads=[
                {
                    "input_count": len(raw_items),
                    "output_count": len(deduped_items),
                    "source_count": len(selected_sources),
                }
            ],
            entity_ids=["dedupe_raw"],
        )
        record_raw_batch(context, deduped_items)

        degraded_reasons = list(errors)
        if not deduped_items:
            degraded_reasons = list(dict.fromkeys(degraded_reasons + ["no_news_collected"]))

        return CollectedNewsBatch(
            window=context.window,
            scopes=list(context.scopes),
            sources=[source.name for source in selected_sources],
            raw_items=deduped_items,
            degraded_reasons=degraded_reasons,
        )
