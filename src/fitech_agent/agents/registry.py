from __future__ import annotations

from pathlib import Path

from .base import AgentDescriptor

_ROOT = Path(__file__).resolve().parent


def _descriptor(
    agent_id: str,
    display_name: str,
    *,
    substages: tuple[str, ...],
) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        display_name=display_name,
        skill_path=_ROOT / agent_id / "skill.md",
        default_route_name=agent_id,
        substages=substages,
    )


CORE_AGENT_DESCRIPTORS: tuple[AgentDescriptor, ...] = (
    _descriptor(
        "ingestion",
        "Ingestion",
        substages=("select_sources", "collect", "dedupe_raw", "record_raw"),
    ),
    _descriptor(
        "event_intelligence",
        "Event Intelligence",
        substages=("normalize", "extract", "translate_or_summarize", "score_credibility"),
    ),
    _descriptor(
        "market_reasoning",
        "Market Reasoning",
        substages=("map_assets", "filter_scope", "analyze_domains", "integrate_strategy"),
    ),
    _descriptor(
        "audit",
        "Audit",
        substages=("audit_publishability", "downgrade_trace", "degraded_reason_merge"),
    ),
    _descriptor(
        "report",
        "Report",
        substages=("compose_brief", "render_markdown", "render_pdf", "persist_report"),
    ),
)

CORE_AGENT_LOOKUP = {descriptor.agent_id: descriptor for descriptor in CORE_AGENT_DESCRIPTORS}


def get_agent_descriptor(agent_id: str) -> AgentDescriptor:
    return CORE_AGENT_LOOKUP[agent_id]
