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
                )
            ],
            audit=AuditSettings(),
            model_route=ModelRoute(),
            run_defaults=RunDefaults(),
        )

    def test_bootstrap_payload_exposes_dashboard_metadata(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            payload = DashboardService(self._build_config(runtime_dir)).bootstrap_payload()
            self.assertEqual(payload["title"], "Fintech Agent 控盘台")
            self.assertEqual(payload["defaults"]["mode"], "full_report")
            self.assertEqual(payload["sources"][0]["name"], "bootstrap_sample")
            self.assertEqual(len(payload["workflow"]), 5)
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


if __name__ == "__main__":
    unittest.main()
