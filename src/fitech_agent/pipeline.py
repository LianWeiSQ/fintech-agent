from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters import build_adapter
from .agents.audit import EvidenceAuditAgent
from .agents.collector import NewsCollectionAgent
from .agents.credibility import CredibilityAgent
from .agents.domain import DomainAnalysisAgent
from .agents.extract import EventExtractionAgent
from .agents.mapping import AssetMappingAgent
from .agents.normalize import NormalizationAgent
from .agents.report import ReportGenerationAgent
from .agents.strategy import StrategyIntegrationAgent
from .config import AppConfig, SourceDefinition
from .llm import LiteLLMClient
from .models import (
    ALL_RESEARCH_SCOPES,
    CanonicalNewsEvent,
    EventAssetMap,
    IntegratedView,
    NewsWindow,
    ResearchRunRequest,
    ResearchRunResult,
    RunMode,
)
from .orchestration import build_graph
from .reporting import render_markdown, save_report_artifacts
from .storage import SQLiteStorage
from .utils import parse_iso_datetime, to_json

MODE_ALIASES = {
    "full_report": "full_report",
    "full-report": "full_report",
    "collect_only": "collect_only",
    "collect-only": "collect_only",
}

DIRECT_ASSET_SCOPES = {
    "equity",
    "commodities",
    "precious_metals",
    "crude_oil",
    "usd",
    "ust",
}

THEMATIC_SCOPES = {
    "risk_sentiment",
    "cn_policy",
    "global_macro",
}


def _empty_integrated_view() -> IntegratedView:
    return IntegratedView([], [], [], [], [], [], [])


class ResearchPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.storage = SQLiteStorage(config.database_path)
        self.storage.initialize()
        self.enabled_sources = [source for source in config.sources if source.enabled]
        self.llm_client = LiteLLMClient(config.model_route)
        self.normalizer = NormalizationAgent()
        self.extractor = EventExtractionAgent(self.llm_client, config.report_language)
        self.credibility = CredibilityAgent()
        self.mapper = AssetMappingAgent()
        self.domain_analyzer = DomainAnalysisAgent()
        self.strategy = StrategyIntegrationAgent()
        self.audit = EvidenceAuditAgent(config.audit)
        self.reporter = ReportGenerationAgent()
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
        return self._coerce_timestamp(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

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
        }

    def _execute_without_graph(self, state: dict[str, Any]) -> dict[str, Any]:
        state.update(self.start_run_node(state))
        state.update(self.collect_news_node(state))
        if state["mode"] == "collect_only":
            state.update(self.finish_collect_only_node(state))
            return state
        for node in (
            self.normalize_news_node,
            self.extract_events_node,
            self.score_credibility_node,
            self.map_assets_node,
            self.filter_scope_node,
            self.analyze_domains_node,
            self.integrate_strategy_node,
            self.audit_evidence_node,
            self.generate_report_node,
        ):
            state.update(node(state))
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

    def collect_news_node(self, state: dict[str, Any]) -> dict[str, Any]:
        selected_sources = self._select_sources(state["sources"])
        collector = NewsCollectionAgent([build_adapter(source) for source in selected_sources])
        raw_items, errors = collector.run(state["window"])
        if not raw_items:
            errors = list(dict.fromkeys(errors + ["no_news_collected"]))
        self.storage.record_stage(
            state["run_id"],
            stage="collect_news",
            entity_type="raw_news_item",
            payloads=raw_items,
            entity_ids=[item.id for item in raw_items],
        )
        return {
            "raw_items": raw_items,
            "degraded_reasons": list(dict.fromkeys(state["degraded_reasons"] + errors)),
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

    def normalize_news_node(self, state: dict[str, Any]) -> dict[str, Any]:
        clusters = self.normalizer.run(state["raw_items"])
        self.storage.record_stage(
            state["run_id"],
            stage="normalize_news",
            entity_type="news_cluster",
            payloads=clusters,
            entity_ids=[cluster.id for cluster in clusters],
        )
        return {"clusters": clusters}

    def extract_events_node(self, state: dict[str, Any]) -> dict[str, Any]:
        events = self.extractor.run(state["clusters"])
        self.storage.record_stage(
            state["run_id"],
            stage="extract_events",
            entity_type="canonical_news_event",
            payloads=events,
            entity_ids=[event.id for event in events],
        )
        return {"events": events}

    def score_credibility_node(self, state: dict[str, Any]) -> dict[str, Any]:
        scores = self.credibility.run(state["events"])
        self.storage.record_stage(
            state["run_id"],
            stage="score_credibility",
            entity_type="credibility_score",
            payloads=scores,
            entity_ids=[score.event_id for score in scores],
        )
        return {"credibility_scores": scores}

    def map_assets_node(self, state: dict[str, Any]) -> dict[str, Any]:
        mappings = self.mapper.run(state["events"])
        self.storage.record_stage(
            state["run_id"],
            stage="map_assets",
            entity_type="event_asset_map",
            payloads=mappings,
            entity_ids=[mapping.event_id for mapping in mappings],
        )
        return {"mappings": mappings}

    def _mapping_scopes(
        self,
        event: CanonicalNewsEvent,
        mapping: EventAssetMap,
    ) -> set[str]:
        scopes: set[str] = set()
        for asset in mapping.assets:
            if asset.startswith("cn_equities/"):
                scopes.add("equity")
            if asset.startswith("cn_futures/"):
                scopes.add("commodities")
            if asset.startswith("precious_metals/"):
                scopes.add("precious_metals")
            if asset.startswith("energy/"):
                scopes.add("crude_oil")
            if asset == "macro/usd":
                scopes.add("usd")
            if asset == "macro/us_rates":
                scopes.add("ust")
            if asset == "macro/cny":
                scopes.add("cn_policy")
        for factor in mapping.macro_factors:
            if factor in {"risk_appetite", "safe_haven_flow"}:
                scopes.add("risk_sentiment")
            if factor in {"policy_support", "china_growth"}:
                scopes.add("cn_policy")
            if factor in {"usd_liquidity", "global_yields", "inflation_expectations", "oil_supply"}:
                scopes.add("global_macro")
        if event.event_type == "china_policy":
            scopes.add("cn_policy")
        if event.event_type in {"fomc", "us_cpi", "us_nonfarm", "opec", "energy_supply", "geopolitics", "macro_growth"}:
            scopes.add("global_macro")
        return scopes

    def _asset_scopes(self, asset: str) -> set[str]:
        scopes: set[str] = set()
        if asset.startswith("cn_equities/"):
            scopes.add("equity")
        if asset.startswith("cn_futures/"):
            scopes.add("commodities")
        if asset.startswith("precious_metals/"):
            scopes.add("precious_metals")
        if asset.startswith("energy/"):
            scopes.add("crude_oil")
        if asset == "macro/usd":
            scopes.add("usd")
        if asset == "macro/us_rates":
            scopes.add("ust")
        if asset == "macro/cny":
            scopes.add("cn_policy")
        return scopes

    def _sector_scopes(self, sector: str) -> set[str]:
        if sector.startswith("cn_equities/"):
            return {"equity"}
        return set()

    def filter_scope_node(self, state: dict[str, Any]) -> dict[str, Any]:
        selected_scopes = set(state["scopes"])
        if selected_scopes == set(ALL_RESEARCH_SCOPES):
            return {}

        mapping_lookup = {mapping.event_id: mapping for mapping in state["mappings"]}
        filtered_events = []
        filtered_mappings = []
        for event in state["events"]:
            mapping = mapping_lookup.get(event.id)
            if mapping is None:
                continue
            event_scopes = self._mapping_scopes(event, mapping)
            if not (event_scopes & selected_scopes):
                continue

            thematic_match = bool(event_scopes & selected_scopes & THEMATIC_SCOPES)
            if thematic_match:
                filtered_events.append(event)
                filtered_mappings.append(mapping)
                continue

            filtered_assets = [
                asset
                for asset in mapping.assets
                if self._asset_scopes(asset) & selected_scopes & DIRECT_ASSET_SCOPES
            ]
            if not filtered_assets:
                continue

            filtered_events.append(event)
            filtered_mappings.append(
                EventAssetMap(
                    event_id=mapping.event_id,
                    assets=filtered_assets,
                    sectors=[
                        sector
                        for sector in mapping.sectors
                        if self._sector_scopes(sector) & selected_scopes
                    ],
                    macro_factors=list(mapping.macro_factors),
                    rationale=list(mapping.rationale),
                )
            )
        return {
            "events": filtered_events,
            "mappings": filtered_mappings,
        }

    def analyze_domains_node(self, state: dict[str, Any]) -> dict[str, Any]:
        assessments = self.domain_analyzer.run(
            state["events"],
            state["credibility_scores"],
            state["mappings"],
        )
        self.storage.record_stage(
            state["run_id"],
            stage="analyze_domains",
            entity_type="market_impact_assessment",
            payloads=assessments,
            entity_ids=[assessment.id for assessment in assessments],
        )
        return {"assessments": assessments}

    def integrate_strategy_node(self, state: dict[str, Any]) -> dict[str, Any]:
        integrated_view = self.strategy.run(state["assessments"])
        self.storage.record_stage(
            state["run_id"],
            stage="integrate_strategy",
            entity_type="integrated_view",
            payloads=[integrated_view],
            entity_ids=["integrated_view"],
        )
        return {"integrated_view": integrated_view}

    def audit_evidence_node(self, state: dict[str, Any]) -> dict[str, Any]:
        assessments, audit_notes = self.audit.run(state["assessments"], state["credibility_scores"])
        self.storage.record_stage(
            state["run_id"],
            stage="audit_evidence",
            entity_type="market_impact_assessment",
            payloads=assessments,
            entity_ids=[assessment.id for assessment in assessments],
        )
        return {
            "assessments": assessments,
            "audit_notes": audit_notes,
            "degraded_reasons": list(dict.fromkeys(state["degraded_reasons"] + audit_notes)),
        }

    def generate_report_node(self, state: dict[str, Any]) -> dict[str, Any]:
        report = self.reporter.run(
            run_id=state["run_id"],
            triggered_at=state["triggered_at"],
            mode=state["mode"],
            window=state["window"],
            scopes=state["scopes"],
            sources=state["sources"],
            events=state["events"],
            assessments=state["assessments"],
            integrated_view=state["integrated_view"],
            degraded_reasons=state["degraded_reasons"],
        )
        report.markdown_body = render_markdown(report)
        markdown_path, pdf_path, render_warnings = save_report_artifacts(report, self.config.report_dir)
        if render_warnings:
            report.degraded = True
            report.degraded_reasons = list(dict.fromkeys(report.degraded_reasons + render_warnings))
            report.markdown_body = render_markdown(report)
            Path(markdown_path).write_text(report.markdown_body, encoding="utf-8")
        self.storage.save_report(state["run_id"], report, markdown_path, pdf_path)
        self.storage.finalize_run(
            state["run_id"],
            status="completed",
            degraded=report.degraded,
            degraded_reasons=report.degraded_reasons,
        )
        return {
            "report": report,
            "markdown_path": markdown_path,
            "pdf_path": pdf_path,
            "degraded_reasons": report.degraded_reasons,
        }


NewsPipeline = ResearchPipeline
