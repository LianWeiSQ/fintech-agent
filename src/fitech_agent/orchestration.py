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


def build_graph(pipeline: Any) -> Any | None:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    workflow = StateGraph(PipelineState)
    workflow.add_node("start_run", pipeline.start_run_node)
    workflow.add_node("collect_news", pipeline.collect_news_node)
    workflow.add_node("finish_collect_only", pipeline.finish_collect_only_node)
    workflow.add_node("normalize_news", pipeline.normalize_news_node)
    workflow.add_node("extract_events", pipeline.extract_events_node)
    workflow.add_node("score_credibility", pipeline.score_credibility_node)
    workflow.add_node("map_assets", pipeline.map_assets_node)
    workflow.add_node("filter_scope", pipeline.filter_scope_node)
    workflow.add_node("analyze_domains", pipeline.analyze_domains_node)
    workflow.add_node("integrate_strategy", pipeline.integrate_strategy_node)
    workflow.add_node("audit_evidence", pipeline.audit_evidence_node)
    workflow.add_node("generate_report", pipeline.generate_report_node)
    workflow.set_entry_point("start_run")
    workflow.add_edge("start_run", "collect_news")
    workflow.add_conditional_edges(
        "collect_news",
        lambda state: (
            "finish_collect_only"
            if state.get("mode") == "collect_only"
            else "normalize_news"
        ),
        {
            "finish_collect_only": "finish_collect_only",
            "normalize_news": "normalize_news",
        },
    )
    workflow.add_edge("finish_collect_only", END)
    workflow.add_edge("normalize_news", "extract_events")
    workflow.add_edge("extract_events", "score_credibility")
    workflow.add_edge("score_credibility", "map_assets")
    workflow.add_edge("map_assets", "filter_scope")
    workflow.add_edge("filter_scope", "analyze_domains")
    workflow.add_edge("analyze_domains", "integrate_strategy")
    workflow.add_edge("integrate_strategy", "audit_evidence")
    workflow.add_edge("audit_evidence", "generate_report")
    workflow.add_edge("generate_report", END)
    return workflow.compile()
