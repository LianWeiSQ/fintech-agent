from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_tests_runtime"
TMP_ROOT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.config import AppConfig, AuditSettings, ModelRoute, RunDefaults, SourceDefinition
from fitech_agent.dashboard import DashboardService
from fitech_agent.models import IntegratedView, NewsWindow, RawNewsItem, ResearchRunResult


class DashboardServiceTests(unittest.TestCase):
    def _make_runtime_dir(self) -> Path:
        path = TMP_ROOT / uuid4().hex
        path.mkdir(parents=True, exist_ok=False)
        return path

    def _build_config(self, tmpdir: Path) -> AppConfig:
        sample_path = ROOT / "examples" / "sample_news.json"
        return AppConfig(
            database_path=str((tmpdir / "fitech_agent.db").resolve()),
            report_dir=str((tmpdir / "reports").resolve()),
            sources=[
                SourceDefinition(
                    name="bootstrap_sample",
                    kind="file",
                    endpoint=str(sample_path),
                    language="mixed",
                    tier="tier1_media",
                    enabled=True,
                    tags=["bootstrap"],
                ),
                SourceDefinition(
                    name="ReutersMarketsX",
                    kind="rss",
                    endpoint="https://rsshub.app/twitter/user/ReutersMarkets",
                    language="en",
                    tier="selected_x",
                    enabled=True,
                    tags=["selected_x", "x"],
                ),
                SourceDefinition(
                    name="FedPressAll",
                    kind="rss",
                    endpoint="https://www.federalreserve.gov/feeds/press_all.xml",
                    language="en",
                    tier="official",
                    enabled=True,
                    tags=["official", "macro", "rates"],
                ),
            ],
            audit=AuditSettings(),
            model_route=ModelRoute(),
            run_defaults=RunDefaults(),
        )

    def test_bootstrap_payload_exposes_source_catalog_and_mix(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            payload = DashboardService(self._build_config(runtime_dir)).bootstrap_payload()
            self.assertEqual(payload["title"], "Fintech Agent 研究工作台")
            self.assertEqual(payload["defaults"]["mode"], "full_report")
            self.assertTrue(any(item["name"] == "ReutersMarketsX" for item in payload["sources"]))
            self.assertEqual(len(payload["workflow"]), 5)
            self.assertIn("sourceCatalog", payload)
            self.assertIn("sourceMix", payload)
            self.assertEqual(payload["sourceCatalog"]["totalSources"], 3)
            self.assertTrue(any(item["sourceClass"] == "x_selected" for item in payload["sources"]))
            self.assertEqual(
                [item["sourceClass"] for item in payload["sourceCatalog"]["classes"]],
                ["official", "media", "x_selected"],
            )
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_run_research_returns_frontend_payload_and_supports_run_context_chat(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            service = DashboardService(self._build_config(runtime_dir))
            payload = service.run_research(
                {
                    "prompt": "请给我一份盘前简报，并说明黄金和原油的联动。",
                    "triggeredAt": "2026-03-20T07:00:00+08:00",
                    "mode": "full_report",
                    "lookbackHours": 18,
                    "scopes": ["equity", "commodities", "precious_metals", "crude_oil"],
                    "sources": ["bootstrap_sample"],
                }
            )

            self.assertGreater(payload["meta"]["runId"], 0)
            self.assertEqual(payload["chatHandle"]["runId"], payload["meta"]["runId"])
            self.assertGreater(len(payload["signalCards"]), 0)
            self.assertGreater(len(payload["workflow"]), 0)
            self.assertIn("sourceMix", payload)
            self.assertIn("classes", payload["sourceMix"])
            self.assertIn("auditNotes", payload)
            self.assertIsInstance(payload["auditNotes"], list)
            self.assertGreater(len(payload["reportSections"]), 0)
            self.assertIsNotNone(payload["meta"]["markdownPath"])

            answer = service.answer_question(
                {
                    "question": "最需要盯的风险变量是什么？",
                    "mode": "run_context",
                    "runId": payload["chatHandle"]["runId"],
                }
            )
            self.assertEqual(answer["chatMode"], "run_context")
            self.assertTrue(answer["answer"])
            self.assertGreater(len(answer["nextPrompts"]), 0)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_general_chat_mode_works_without_run_context(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            service = DashboardService(self._build_config(runtime_dir))
            answer = service.answer_question(
                {
                    "question": "这个系统能做什么？",
                    "mode": "general",
                }
            )
            self.assertEqual(answer["chatMode"], "general")
            self.assertTrue(answer["answer"])
            self.assertGreater(len(answer["citations"]), 0)
            self.assertIn("init-db", answer["citations"][0]["source"])
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_collect_only_run_marks_skipped_workflow_and_empty_report_outputs(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            service = DashboardService(self._build_config(runtime_dir))
            payload = service.run_research(
                {
                    "prompt": "先只采集消息。",
                    "triggeredAt": "2026-03-20T07:00:00+08:00",
                    "mode": "collect_only",
                    "lookbackHours": 18,
                    "scopes": ["equity"],
                    "sources": ["bootstrap_sample"],
                }
            )

            self.assertEqual(payload["meta"]["mode"], "collect_only")
            self.assertIsNone(payload["meta"]["markdownPath"])
            self.assertIsNone(payload["meta"]["pdfPath"])
            self.assertEqual(payload["workflow"][0]["status"], "completed")
            self.assertTrue(all(step["status"] == "idle" for step in payload["workflow"][1:]))
            self.assertIn("仅采集", payload["reportSections"][0]["title"])
            self.assertEqual(len(payload["events"]), 0)
            self.assertGreater(len(payload["timeline"]), 0)
            self.assertIn("classes", payload["sourceMix"])
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_resolve_report_file_accepts_generated_markdown_and_rejects_outside_paths(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            service = DashboardService(self._build_config(runtime_dir))
            payload = service.run_research(
                {
                    "prompt": "请给我一份盘前简报。",
                    "triggeredAt": "2026-03-20T07:00:00+08:00",
                    "mode": "full_report",
                    "lookbackHours": 18,
                    "scopes": ["equity", "commodities"],
                    "sources": ["bootstrap_sample"],
                }
            )

            markdown_path, content_type = service.resolve_report_file(payload["meta"]["markdownPath"])
            self.assertTrue(markdown_path.is_file())
            self.assertEqual(content_type, "text/markdown; charset=utf-8")

            outside_path = runtime_dir / "outside.md"
            outside_path.write_text("outside", encoding="utf-8")
            with self.assertRaises(ValueError):
                service.resolve_report_file(str(outside_path))
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_source_mix_prioritizes_official_anchor_over_selected_x(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            service = DashboardService(self._build_config(runtime_dir))
            result = ResearchRunResult(
                run_id=1,
                mode="collect_only",
                triggered_at="2026-03-22T07:00:00+08:00",
                window=NewsWindow(start="2026-03-21T00:00:00Z", end="2026-03-22T00:00:00Z"),
                scopes=["global_macro"],
                sources=["FedPressAll", "ReutersMarketsX"],
                raw_items=[
                    RawNewsItem(
                        id="1",
                        source="FedPressAll",
                        source_type="rss",
                        source_tier="official",
                        language="en",
                        title="Federal Reserve signals policy pause",
                        summary="Official statement keeps rates restrictive.",
                        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260321a.htm",
                        published_at="2026-03-21T10:00:00Z",
                        collected_at="2026-03-21T10:05:00Z",
                        tags=["official"],
                        metadata={"source_confidence_level": "L1", "source_trust_score": 1.0},
                    ),
                    RawNewsItem(
                        id="2",
                        source="ReutersMarketsX",
                        source_type="rss",
                        source_tier="selected_x",
                        language="en",
                        title="Gold traders reassess yields after Fed statement",
                        summary="Curated X headline follows the Fed release.",
                        url="https://x.com/ReutersMarkets/status/1",
                        published_at="2026-03-21T11:00:00Z",
                        collected_at="2026-03-21T11:05:00Z",
                        tags=["x"],
                        metadata={"source_confidence_level": "L3", "source_trust_score": 0.66, "entry_author": "ReutersMarkets"},
                    ),
                ],
                integrated_view=IntegratedView([], [], [], [], [], [], []),
            )
            source_mix = service._build_source_mix(result)
            self.assertEqual(source_mix["totalItems"], 2)
            self.assertEqual(source_mix["topSources"][0]["name"], "FedPressAll")
            self.assertEqual(source_mix["topSources"][0]["sourceClass"], "official")
            selected_x_group = next(item for item in source_mix["classes"] if item["sourceClass"] == "x_selected")
            self.assertEqual(selected_x_group["entries"][0]["name"], "ReutersMarketsX")
            self.assertEqual(selected_x_group["entries"][0]["sourceClassLabel"], "精选 X")
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
