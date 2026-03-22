from __future__ import annotations

from collections import Counter

from ...adapters import build_adapter
from ...models import CollectedNewsBatch, RawNewsItem, ResearchRunRequest
from ..base import AgentRuntimeContext, BaseResearchAgent
from ..registry import get_agent_descriptor
from .runtime import IngestionRuntime
from .steps.collect import NewsCollectionAgent
from .steps.dedupe_raw import dedupe_raw_items
from .steps.record_raw import record_raw_batch
from .steps.select_sources import select_sources


def _count(values: list[str]) -> dict[str, int]:
    return dict(Counter(value for value in values if value))


def _raw_levels(items: list[RawNewsItem]) -> list[str]:
    return [str(item.metadata.get("source_confidence_level", "")) for item in items]


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
                    "selected_tier_counts": _count([source.tier for source in selected_sources]),
                    "selected_level_counts": _count(
                        [source.confidence_level for source in selected_sources]
                    ),
                    "raw_tier_counts": _count([item.source_tier for item in deduped_items]),
                    "raw_level_counts": _count(_raw_levels(deduped_items)),
                    "has_l1_or_l2_source": any(
                        source.confidence_level in {"L1", "L2"}
                        for source in selected_sources
                    ),
                }
            ],
            entity_ids=["dedupe_raw"],
        )
        record_raw_batch(context, deduped_items)

        degraded_reasons = list(errors)
        if selected_sources and not any(
            source.confidence_level in {"L1", "L2"} for source in selected_sources
        ):
            degraded_reasons.append("no_l1_l2_source_anchor")
        if deduped_items and all(item.source_tier in {"social", "unknown"} for item in deduped_items):
            degraded_reasons.append("low_confidence_raw_mix")
        if not deduped_items:
            degraded_reasons = list(dict.fromkeys(degraded_reasons + ["no_news_collected"]))
        else:
            degraded_reasons = list(dict.fromkeys(degraded_reasons))

        return CollectedNewsBatch(
            window=context.window,
            scopes=list(context.scopes),
            sources=[source.name for source in selected_sources],
            raw_items=deduped_items,
            degraded_reasons=degraded_reasons,
        )
