from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .agents.audit.agent import AuditAgent
from .agents.base import AgentRuntimeContext
from .agents.event_intelligence.agent import EventIntelligenceAgent
from .agents.ingestion.agent import IngestionAgent
from .agents.market_reasoning.agent import MarketReasoningAgent
from .agents.registry import CORE_AGENT_DESCRIPTORS, get_agent_descriptor
from .agents.report.agent import ReportAgent
from .agents.skill_loader import AgentSkillLoader
from .config import AppConfig, SourceDefinition
from .llm import LiteLLMClient
from .models import (
    ALL_RESEARCH_SCOPES,
    IntegratedView,
    NewsWindow,
    ResearchRunRequest,
    ResearchRunResult,
    RunMode,
)
from .orchestration import build_graph
from .storage import SQLiteStorage
from .utils import parse_iso_datetime, to_json

MODE_ALIASES = {
    "full_report": "full_report",
    "full-report": "full_report",
    "collect_only": "collect_only",
    "collect-only": "collect_only",
}


def _empty_integrated_view() -> IntegratedView:
    return IntegratedView([], [], [], [], [], [], [])


class ResearchPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.storage = SQLiteStorage(config.database_path)
        self.storage.initialize()
        self.enabled_sources = [source for source in config.sources if source.enabled]
        self.skill_loader = AgentSkillLoader()
        self.agent_descriptors = {
            descriptor.agent_id: descriptor for descriptor in CORE_AGENT_DESCRIPTORS
        }
        self.agent_skills = {
            agent_id: self.skill_loader.load(
                agent_id,
                descriptor.skill_path,
                extra_roots=self.config.skill_dirs,
            )
            for agent_id, descriptor in self.agent_descriptors.items()
        }
        self.agent_clients = {
            agent_id: LiteLLMClient(config.resolve_model_route(agent_id))
            for agent_id in self.agent_descriptors
        }
        self.llm_client = LiteLLMClient(config.resolve_model_route())
        for preferred_agent in ("report", "market_reasoning", "event_intelligence"):
            candidate = self.agent_clients[preferred_agent]
            if candidate.available:
                self.llm_client = candidate
                break
        self.ingestion_agent = IngestionAgent()
        self.event_intelligence_agent = EventIntelligenceAgent(config.report_language)
        self.market_reasoning_agent = MarketReasoningAgent()
        self.audit_agent = AuditAgent()
        self.report_agent = ReportAgent()
        self.graph = build_graph(self)

    def _local_timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.config.timezone)
        except ZoneInfoNotFoundError:
            if self.config.timezone == "Asia/Shanghai":
                return timezone(timedelta(hours=8), name="Asia/Shanghai")
            if self.config.timezone in {"UTC", "Etc/UTC"}:
                return timezone.utc
            raise

    def _coerce_timestamp(self, value: str) -> datetime:
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid ISO timestamp: {value}") from exc
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=self._local_timezone())
        return timestamp.astimezone(self._local_timezone()).replace(microsecond=0)

    def _to_utc_window_value(self, value: str) -> str:
        return (
            self._coerce_timestamp(value)
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _default_triggered_at(self) -> str:
        return datetime.now(self._local_timezone()).replace(second=0, microsecond=0).isoformat()

    def _normalize_mode(self, mode: str | None) -> RunMode:
        raw_mode = (mode or self.config.run_defaults.mode or "full_report").strip().lower()
        normalized = MODE_ALIASES.get(raw_mode)
        if normalized is None:
            raise ValueError(f"Unsupported run mode: {mode}")
        return normalized  # type: ignore[return-value]

    def _normalize_scopes(self, scopes: list[str] | None) -> list[str]:
        normalized_input = [item.strip().lower() for item in (scopes or []) if item.strip()]
        if not normalized_input:
            return list(ALL_RESEARCH_SCOPES)
        invalid = [item for item in normalized_input if item not in ALL_RESEARCH_SCOPES]
        if invalid:
            raise ValueError(f"Unsupported scope: {', '.join(sorted(dict.fromkeys(invalid)))}")
        selected = set(normalized_input)
        return [scope for scope in ALL_RESEARCH_SCOPES if scope in selected]

    def _select_sources(self, requested_sources: list[str] | None) -> list[SourceDefinition]:
        if not requested_sources:
            return list(self.enabled_sources)

        requested_lookup = {
            source_name.strip().lower(): source_name.strip()
            for source_name in requested_sources
            if source_name.strip()
        }
        configured_lookup = {
            source.name.strip().lower(): source
            for source in self.enabled_sources
        }
        missing = [
            original
            for key, original in requested_lookup.items()
            if key not in configured_lookup
        ]
        if missing:
            raise ValueError(f"Unknown source: {', '.join(sorted(missing))}")

        return [
            source
            for source in self.enabled_sources
            if source.name.strip().lower() in requested_lookup
        ]

    def build_request(
        self,
        request: ResearchRunRequest | str | None = None,
    ) -> ResearchRunRequest:
        if isinstance(request, str):
            request = ResearchRunRequest(triggered_at=request)
        if request is None:
            request = ResearchRunRequest()

        mode = self._normalize_mode(request.mode)
        if bool(request.window_start) ^ bool(request.window_end):
            raise ValueError("window_start and window_end must be provided together.")

        triggered_at = self._coerce_timestamp(
            request.triggered_at or self._default_triggered_at()
        ).isoformat()

        if request.window_start and request.window_end:
            window_start = self._to_utc_window_value(request.window_start)
            window_end = self._to_utc_window_value(request.window_end)
            if parse_iso_datetime(window_start) >= parse_iso_datetime(window_end):
                raise ValueError("window_start must be earlier than window_end.")
            lookback_hours = request.lookback_hours
        else:
            lookback_hours = (
                request.lookback_hours
                if request.lookback_hours is not None
                else self.config.run_defaults.lookback_hours
            )
            if lookback_hours is None or lookback_hours <= 0:
                raise ValueError("lookback_hours must be a positive integer.")
            triggered_dt = parse_iso_datetime(triggered_at)
            assert triggered_dt is not None
            window_start = (
                (triggered_dt - timedelta(hours=lookback_hours))
                .astimezone(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
            window_end = (
                triggered_dt.astimezone(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )

        scopes = self._normalize_scopes(request.scopes)
        selected_sources = self._select_sources(request.sources)
        return ResearchRunRequest(
            mode=mode,
            triggered_at=triggered_at,
            lookback_hours=lookback_hours,
            window_start=window_start,
            window_end=window_end,
            scopes=scopes,
            sources=[source.name for source in selected_sources],
        )

    def _initial_state(self, request: ResearchRunRequest) -> dict[str, Any]:
        return {
            "mode": request.mode,
            "triggered_at": request.triggered_at,
            "window": NewsWindow(request.window_start or "", request.window_end or ""),
            "scopes": list(request.scopes),
            "sources": list(request.sources),
            "raw_items": [],
            "clusters": [],
            "events": [],
            "credibility_scores": [],
            "mappings": [],
            "assessments": [],
            "integrated_view": _empty_integrated_view(),
            "degraded_reasons": [],
            "audit_notes": [],
            "markdown_path": None,
            "pdf_path": None,
            "collected_batch": None,
            "event_intelligence_bundle": None,
            "market_reasoning_bundle": None,
            "audit_bundle": None,
            "report_bundle": None,
        }

    def _build_agent_context(self, agent_id: str, state: dict[str, Any]) -> AgentRuntimeContext:
        descriptor = get_agent_descriptor(agent_id)
        return AgentRuntimeContext(
            run_id=state["run_id"],
            mode=state["mode"],
            triggered_at=state["triggered_at"],
            window=state["window"],
            scopes=list(state["scopes"]),
            sources=list(state["sources"]),
            config=self.config,
            storage=self.storage,
            llm_client=self.agent_clients[agent_id],
            descriptor=descriptor,
            skill=self.agent_skills[agent_id],
        )

    def compose_agent_system_prompt(self, agent_id: str, instruction: str) -> str:
        skill = self.agent_skills.get(agent_id)
        skill_context = skill.prompt_context() if skill is not None else ""
        if not skill_context:
            return instruction
        return f"{instruction}\n\nAgent skill instructions:\n{skill_context}"

    def _execute_without_graph(self, state: dict[str, Any]) -> dict[str, Any]:
        state.update(self.start_run_node(state))
        state.update(self.ingestion_node(state))
        if state["mode"] == "collect_only":
            state.update(self.finish_collect_only_node(state))
            return state
        state.update(self.event_intelligence_node(state))
        state.update(self.market_reasoning_node(state))
        state.update(self.audit_node(state))
        state.update(self.report_node(state))
        return state

    def _result_from_state(self, state: dict[str, Any]) -> ResearchRunResult:
        return ResearchRunResult(
            run_id=state["run_id"],
            mode=state["mode"],
            triggered_at=state["triggered_at"],
            window=state["window"],
            scopes=list(state["scopes"]),
            sources=list(state["sources"]),
            raw_items=list(state.get("raw_items", [])),
            clusters=list(state.get("clusters", [])),
            events=list(state.get("events", [])),
            credibility_scores=list(state.get("credibility_scores", [])),
            mappings=list(state.get("mappings", [])),
            assessments=list(state.get("assessments", [])),
            integrated_view=state.get("integrated_view", _empty_integrated_view()),
            audit_notes=list(state.get("audit_notes", [])),
            degraded_reasons=list(state.get("degraded_reasons", [])),
            report=state.get("report"),
            markdown_path=state.get("markdown_path"),
            pdf_path=state.get("pdf_path"),
        )

    def run(self, request: ResearchRunRequest | str | None = None) -> ResearchRunResult:
        resolved_request = self.build_request(request)
        state = self._initial_state(resolved_request)
        try:
            if self.graph is not None:
                state = self.graph.invoke(state)
            else:
                state = self._execute_without_graph(state)
            return self._result_from_state(state)
        except Exception:
            run_id = state.get("run_id")
            if run_id:
                self.storage.finalize_run(
                    run_id,
                    status="failed",
                    degraded=True,
                    degraded_reasons=state.get("degraded_reasons", []) + ["pipeline_failed"],
                )
            raise

    def run_request(self, request: ResearchRunRequest | None = None) -> ResearchRunResult:
        return self.run(request)

    def start_run_node(self, state: dict[str, Any]) -> dict[str, Any]:
        config_payload = {
            "app_config": asdict(self.config),
            "runtime": {
                "mode": state["mode"],
                "triggered_at": state["triggered_at"],
                "window": state["window"],
                "scopes": state["scopes"],
                "sources": state["sources"],
            },
        }
        run_id = self.storage.create_run(
            triggered_at=state["triggered_at"],
            mode=state["mode"],
            window_start=state["window"].start,
            window_end=state["window"].end,
            scopes=state["scopes"],
            sources=state["sources"],
            config_json=to_json(config_payload),
        )
        return {"run_id": run_id}

    def ingestion_node(self, state: dict[str, Any]) -> dict[str, Any]:
        context = self._build_agent_context("ingestion", state)
        request = ResearchRunRequest(
            mode=state["mode"],
            triggered_at=state["triggered_at"],
            window_start=state["window"].start,
            window_end=state["window"].end,
            scopes=list(state["scopes"]),
            sources=list(state["sources"]),
        )
        batch = self.ingestion_agent.run(context, request)
        return {
            "collected_batch": batch,
            "raw_items": batch.raw_items,
            "sources": list(batch.sources),
            "degraded_reasons": list(dict.fromkeys(state["degraded_reasons"] + batch.degraded_reasons)),
        }

    def finish_collect_only_node(self, state: dict[str, Any]) -> dict[str, Any]:
        self.storage.finalize_run(
            state["run_id"],
            status="completed",
            degraded=bool(state["degraded_reasons"]),
            degraded_reasons=state["degraded_reasons"],
        )
        return {
            "integrated_view": state.get("integrated_view", _empty_integrated_view()),
            "markdown_path": None,
            "pdf_path": None,
        }

    def event_intelligence_node(self, state: dict[str, Any]) -> dict[str, Any]:
        context = self._build_agent_context("event_intelligence", state)
        bundle = self.event_intelligence_agent.run(context, state["collected_batch"])
        return {
            "event_intelligence_bundle": bundle,
            "clusters": bundle.clusters,
            "events": bundle.events,
            "credibility_scores": bundle.credibility_scores,
        }

    def market_reasoning_node(self, state: dict[str, Any]) -> dict[str, Any]:
        context = self._build_agent_context("market_reasoning", state)
        bundle = self.market_reasoning_agent.run(context, state["event_intelligence_bundle"])
        return {
            "market_reasoning_bundle": bundle,
            "events": bundle.intelligence.events,
            "credibility_scores": bundle.intelligence.credibility_scores,
            "mappings": bundle.mappings,
            "assessments": bundle.assessments,
            "integrated_view": bundle.integrated_view,
        }

    def audit_node(self, state: dict[str, Any]) -> dict[str, Any]:
        context = self._build_agent_context("audit", state)
        bundle = self.audit_agent.run(context, state["market_reasoning_bundle"])
        return {
            "audit_bundle": bundle,
            "assessments": bundle.assessments,
            "audit_notes": bundle.audit_notes,
            "degraded_reasons": bundle.degraded_reasons,
        }

    def report_node(self, state: dict[str, Any]) -> dict[str, Any]:
        context = self._build_agent_context("report", state)
        bundle = self.report_agent.run(context, state["audit_bundle"])
        return {
            "report_bundle": bundle,
            "report": bundle.report,
            "markdown_path": bundle.markdown_path,
            "pdf_path": bundle.pdf_path,
            "degraded_reasons": list(bundle.report.degraded_reasons if bundle.report else state["degraded_reasons"]),
        }


NewsPipeline = ResearchPipeline
