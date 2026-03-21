from __future__ import annotations

from ...base import AgentRuntimeContext
from ....models import RawNewsItem


def record_raw_batch(context: AgentRuntimeContext, raw_items: list[RawNewsItem]) -> None:
    context.storage.record_stage(
        context.run_id,
        stage="ingestion",
        agent_id="ingestion",
        substage="record_raw",
        entity_type="raw_news_item",
        payloads=raw_items,
        entity_ids=[item.id for item in raw_items],
    )
