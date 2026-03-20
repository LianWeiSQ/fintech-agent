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

from news_employee.config import AppConfig, AuditSettings, ModelRoute, SourceDefinition
from news_employee.pipeline import NewsPipeline


class PipelineTests(unittest.TestCase):
    def _build_config(self, tmpdir: Path, include_failing_source: bool = False) -> AppConfig:
        sample_path = ROOT / "examples" / "sample_news.json"
        sources = [
            SourceDefinition(
                name="bootstrap_sample",
                kind="file",
                endpoint=str(sample_path),
                language="mixed",
                tier="tier1_media",
                enabled=True,
                tags=["bootstrap"],
            )
        ]
        if include_failing_source:
            sources.append(
                SourceDefinition(
                    name="failing_mock",
                    kind="mock",
                    endpoint="error",
                    language="en",
                    tier="tier1_media",
                    enabled=True,
                    tags=["failure"],
                )
            )
        return AppConfig(
            database_path=str((tmpdir / "news_employee.db").resolve()),
            report_dir=str((tmpdir / "reports").resolve()),
            sources=sources,
            audit=AuditSettings(),
            model_route=ModelRoute(),
        )

    def _make_runtime_dir(self) -> Path:
        path = TMP_ROOT / uuid4().hex
        path.mkdir(parents=True, exist_ok=False)
        return path

    def test_pipeline_generates_report_artifacts(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = NewsPipeline(config).run("2026-03-20T07:00:00+08:00")
            self.assertTrue(Path(result["markdown_path"]).exists())
            self.assertGreater(len(result["report"].cross_asset_themes), 0)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_pipeline_degrades_but_completes_when_one_source_fails(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir, include_failing_source=True)
            result = NewsPipeline(config).run("2026-03-20T07:00:00+08:00")
            joined = "\n".join(result["degraded_reasons"])
            self.assertIn("source_failed:failing_mock", joined)
            self.assertTrue(Path(result["markdown_path"]).exists())
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
