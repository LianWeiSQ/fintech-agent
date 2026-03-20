from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
from .config import AppConfig
from .llm import LiteLLMClient
from .models import IntegratedView, NewsWindow
from .orchestration import build_graph
from .reporting import render_markdown, save_report_artifacts
from .storage import SQLiteStorage
from .utils import to_json


class NewsPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.storage = SQLiteStorage(config.database_path)
        self.storage.initialize()
        adapters = [build_adapter(source) for source in config.sources if source.enabled]
        self.collector = NewsCollectionAgent(adapters)
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

    def _default_scheduled_for(self) -> str:
        local_now = datetime.now(ZoneInfo(self.config.timezone)).replace(second=0, microsecond=0)
        return local_now.isoformat()

    def _make_window(self, scheduled_for: str) -> NewsWindow:
        timestamp = datetime.fromisoformat(scheduled_for)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=ZoneInfo(self.config.timezone))
        start = timestamp - timedelta(hours=18)
        return NewsWindow(
            start=start.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            end=timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )

    def _initial_state(self, scheduled_for: str | None = None) -> dict[str, Any]:
        resolved = scheduled_for or self._default_scheduled_for()
        return {
            "scheduled_for": resolved,
            "window": self._make_window(resolved),
            "raw_items": [],
            "clusters": [],
            "events": [],
            "credibility_scores": [],
            "mappings": [],
            "assessments": [],
            "integrated_view": IntegratedView([], [], [], [], [], [], []),
            "degraded_reasons": [],
            "audit_notes": [],
        }

    def run(self, scheduled_for: str | None = None) -> dict[str, Any]:
        state = self._initial_state(scheduled_for)
        try:
            if self.graph is not None:
                return self.graph.invoke(state)
            for node in (
                self.start_run_node,
                self.collect_news_node,
                self.normalize_news_node,
                self.extract_events_node,
                self.score_credibility_node,
                self.map_assets_node,
                self.analyze_domains_node,
                self.integrate_strategy_node,
                self.audit_evidence_node,
                self.generate_report_node,
            ):
                state.update(node(state))
            return state
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

    def start_run_node(self, state: dict[str, Any]) -> dict[str, Any]:
        run_id = self.storage.create_run(state["scheduled_for"], to_json(asdict(self.config)))
        return {"run_id": run_id}

    def collect_news_node(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_items, errors = self.collector.run(state["window"])
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
            scheduled_for=state["scheduled_for"],
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
