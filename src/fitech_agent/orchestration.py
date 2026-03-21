from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    mode: str
    triggered_at: str
    window: Any
    scopes: list[str]
    sources: list[str]
    run_id: int
    raw_items: list[Any]
    clusters: list[Any]
    events: list[Any]
    credibility_scores: list[Any]
    mappings: list[Any]
    assessments: list[Any]
    integrated_view: Any
    report: Any
    markdown_path: str | None
    pdf_path: str | None
    degraded_reasons: list[str]
    audit_notes: list[str]
    collected_batch: Any
    event_intelligence_bundle: Any
    market_reasoning_bundle: Any
    audit_bundle: Any
    report_bundle: Any


def build_graph(pipeline: Any) -> Any | None:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    workflow = StateGraph(PipelineState)
    workflow.add_node("start_run", pipeline.start_run_node)
    workflow.add_node("ingestion", pipeline.ingestion_node)
    workflow.add_node("finish_collect_only", pipeline.finish_collect_only_node)
    workflow.add_node("event_intelligence", pipeline.event_intelligence_node)
    workflow.add_node("market_reasoning", pipeline.market_reasoning_node)
    workflow.add_node("audit", pipeline.audit_node)
    workflow.add_node("report", pipeline.report_node)
    workflow.set_entry_point("start_run")
    workflow.add_edge("start_run", "ingestion")
    workflow.add_conditional_edges(
        "ingestion",
        lambda state: (
            "finish_collect_only"
            if state.get("mode") == "collect_only"
            else "event_intelligence"
        ),
        {
            "finish_collect_only": "finish_collect_only",
            "event_intelligence": "event_intelligence",
        },
    )
    workflow.add_edge("finish_collect_only", END)
    workflow.add_edge("event_intelligence", "market_reasoning")
    workflow.add_edge("market_reasoning", "audit")
    workflow.add_edge("audit", "report")
    workflow.add_edge("report", END)
    return workflow.compile()
