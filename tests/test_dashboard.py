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
from fitech_agent.models import IntegratedView, NewsWindow, ResearchRunResult, RawNewsItem


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
                    tier="tier1_media",
                    enabled=True,
                    tags=["wire", "x"],
                ),
                SourceDefinition(
                    name="RedditEconomicsRatesMacro",
                    kind="rss",
                    endpoint="https://old.reddit.com/r/Economics/search.rss?q=fed",
                    language="en",
                    tier="social",
                    enabled=True,
                    tags=["social", "reddit"],
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
            self.assertEqual(payload["title"], "Fintech Agent 控制台")
            self.assertEqual(payload["defaults"]["mode"], "full_report")
            self.assertTrue(any(item["name"] == "ReutersMarketsX" for item in payload["sources"]))
            self.assertEqual(len(payload["workflow"]), 5)
            self.assertIn("sourceCatalog", payload)
            self.assertIn("sourceMix", payload)
            self.assertTrue(any(item["channel"] == "x" for item in payload["sourceCatalog"]["channels"]))
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_run_research_returns_frontend_payload_and_allows_follow_up(self) -> None:
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
            self.assertTrue(payload["assistantOpening"]["text"])
            self.assertGreater(len(payload["domainBoards"]), 0)
            self.assertEqual(payload["chatHandle"]["runId"], payload["meta"]["runId"])
            self.assertIn("sourceMix", payload)
            self.assertEqual(payload["sourceMix"]["levels"][1]["level"], "L2")

            answer = service.answer_question(
                {
                    "question": "最需要盯的风险变量是什么？",
                    "runId": payload["chatHandle"]["runId"],
                }
            )
            self.assertEqual(answer["mode"], "fallback")
            self.assertIn("观察变量", answer["answer"])
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_source_mix_extracts_x_and_reddit_hotspots(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            service = DashboardService(self._build_config(runtime_dir))
            result = ResearchRunResult(
                run_id=1,
                mode="collect_only",
                triggered_at="2026-03-22T07:00:00+08:00",
                window=NewsWindow(start="2026-03-21T00:00:00Z", end="2026-03-22T00:00:00Z"),
                scopes=["global_macro"],
                sources=["ReutersMarketsX", "RedditEconomicsRatesMacro"],
                raw_items=[
                    RawNewsItem(
                        id="1",
                        source="ReutersMarketsX",
                        source_type="rss",
                        source_tier="tier1_media",
                        language="en",
                        title="Fed pricing shifts after CPI",
                        summary="Rates reprice higher.",
                        url="https://x.com/ReutersMarkets/status/1",
                        published_at="2026-03-21T10:00:00Z",
                        collected_at="2026-03-21T10:05:00Z",
                        tags=["x"],
                        metadata={"source_confidence_level": "L2", "source_trust_score": 0.88, "entry_author": "ReutersMarkets"},
                    ),
                    RawNewsItem(
                        id="2",
                        source="RedditEconomicsRatesMacro",
                        source_type="rss",
                        source_tier="social",
                        language="en",
                        title="Fed thread with Reuters link",
                        summary="Discussion with primary-source links.",
                        url="https://old.reddit.com/r/Economics/comments/abc",
                        published_at="2026-03-21T11:00:00Z",
                        collected_at="2026-03-21T11:05:00Z",
                        tags=["reddit"],
                        metadata={"source_confidence_level": "L4", "source_trust_score": 0.38, "entry_author": "macro_mod"},
                    ),
                ],
                integrated_view=IntegratedView([], [], [], [], [], [], []),
            )
            source_mix = service._build_source_mix(result)
            self.assertEqual(source_mix["totalItems"], 2)
            self.assertEqual(source_mix["channels"][0]["channel"], "x")
            self.assertEqual(source_mix["channels"][0]["entries"][0]["name"], "ReutersMarkets")
            self.assertEqual(source_mix["channels"][1]["channel"], "reddit")
            self.assertEqual(source_mix["channels"][1]["entries"][0]["name"], "macro_mod")
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
