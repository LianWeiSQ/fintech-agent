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
from fitech_agent.evaluation import ForecastEvaluator, load_price_observations
from fitech_agent.agents.skill_loader import AgentSkillLoader
from fitech_agent.models import ResearchRunRequest
from fitech_agent.pipeline import NewsPipeline, ResearchPipeline
from fitech_agent.storage import SQLiteStorage


class PipelineTests(unittest.TestCase):
    def _build_config(
        self,
        tmpdir: Path,
        *,
        include_failing_source: bool = False,
        run_defaults: RunDefaults | None = None,
    ) -> AppConfig:
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
            database_path=str((tmpdir / "fitech_agent.db").resolve()),
            report_dir=str((tmpdir / "reports").resolve()),
            sources=sources,
            audit=AuditSettings(),
            model_route=ModelRoute(),
            run_defaults=run_defaults or RunDefaults(),
        )

    def _make_runtime_dir(self) -> Path:
        path = TMP_ROOT / uuid4().hex
        path.mkdir(parents=True, exist_ok=False)
        return path

    def test_news_pipeline_alias_points_to_research_pipeline(self) -> None:
        self.assertIs(NewsPipeline, ResearchPipeline)

    def test_pipeline_generates_research_artifacts(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(triggered_at="2026-03-20T07:00:00+08:00")
            )
            self.assertIsNotNone(result.report)
            self.assertIsNotNone(result.markdown_path)
            self.assertTrue(Path(result.markdown_path or "").exists())
            self.assertIn("research_run_", Path(result.markdown_path or "").name)
            self.assertGreater(len(result.report.cross_asset_themes), 0)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_collect_only_completes_without_report_artifacts(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(
                    mode="collect_only",
                    triggered_at="2026-03-20T07:00:00+08:00",
                )
            )
            self.assertIsNone(result.report)
            self.assertIsNone(result.markdown_path)
            self.assertIsNone(result.pdf_path)
            self.assertGreater(len(result.raw_items), 0)

            storage = SQLiteStorage(config.database_path)
            with storage.connect() as conn:
                report_rows = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            self.assertEqual(report_rows, 0)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_scope_filter_limits_downstream_assessments(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(
                    triggered_at="2026-03-20T07:00:00+08:00",
                    scopes=["equity"],
                )
            )
            self.assertGreater(len(result.events), 0)
            self.assertGreater(len(result.assessments), 0)
            self.assertEqual({item.domain for item in result.assessments}, {"equities"})
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_source_allowlist_only_filters_collection(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir, include_failing_source=True)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(
                    triggered_at="2026-03-20T07:00:00+08:00",
                    sources=["bootstrap_sample"],
                )
            )
            self.assertGreater(len(result.raw_items), 0)
            self.assertNotIn("failing_mock", "\n".join(result.degraded_reasons))
            self.assertEqual(result.sources, ["bootstrap_sample"])
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_explicit_window_overrides_lookback(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(
                    triggered_at="2026-03-20T09:00:00+08:00",
                    lookback_hours=1,
                    window_start="2026-03-18T00:00:00+08:00",
                    window_end="2026-03-20T08:00:00+08:00",
                )
            )
            self.assertEqual(result.window.start, "2026-03-17T16:00:00Z")
            self.assertEqual(result.window.end, "2026-03-20T00:00:00Z")
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_run_defaults_can_control_mode(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(
                runtime_dir,
                run_defaults=RunDefaults(mode="collect_only", lookback_hours=12),
            )
            result = ResearchPipeline(config).run(
                ResearchRunRequest(triggered_at="2026-03-20T07:00:00+08:00")
            )
            self.assertEqual(result.mode, "collect_only")
            self.assertIsNone(result.report)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_pipeline_degrades_but_completes_when_one_source_fails(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir, include_failing_source=True)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(triggered_at="2026-03-20T07:00:00+08:00")
            )
            joined = "\n".join(result.degraded_reasons)
            self.assertIn("source_failed:failing_mock", joined)
            self.assertIsNotNone(result.markdown_path)
            self.assertTrue(Path(result.markdown_path or "").exists())
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_evaluation_reads_audited_assessments_without_duplicates(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(triggered_at="2026-03-20T07:00:00+08:00")
            )
            storage = SQLiteStorage(config.database_path)
            assessments = storage.load_assessments(result.run_id)
            self.assertEqual(len({item.id for item in assessments}), len(assessments))

            observations = load_price_observations(ROOT / "examples" / "sample_price_observations.csv")
            outcomes = ForecastEvaluator().evaluate(result.run_id, assessments, observations)
            storage.record_outcomes(result.run_id, outcomes)

            for outcome in outcomes:
                self.assertIn(outcome.evaluation_window, {"D0", "D1", "D5"})
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


    def test_full_report_records_core_agents_and_substages(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config = self._build_config(runtime_dir)
            result = ResearchPipeline(config).run(
                ResearchRunRequest(triggered_at="2026-03-20T07:00:00+08:00")
            )
            storage = SQLiteStorage(config.database_path)
            with storage.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT agent_id, substage
                    FROM stage_payloads
                    WHERE run_id = ?
                    ORDER BY agent_id, substage
                    """,
                    (result.run_id,),
                ).fetchall()
            agent_ids = {row[0] for row in rows}
            substages = {row[1] for row in rows}
            self.assertEqual(
                agent_ids,
                {"ingestion", "event_intelligence", "market_reasoning", "audit", "report"},
            )
            self.assertIn("normalize", substages)
            self.assertIn("persist_report", substages)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_core_agent_skills_load_from_agent_directories(self) -> None:
        loader = AgentSkillLoader()
        root = ROOT / "src" / "fitech_agent" / "agents"
        for agent_id in (
            "ingestion",
            "event_intelligence",
            "market_reasoning",
            "audit",
            "report",
        ):
            spec = loader.load(agent_id, root / agent_id / "skill.md")
            self.assertTrue(spec.exists)
            self.assertEqual(spec.metadata.get("agent_id"), agent_id)
            self.assertTrue(spec.body)

    def test_overlay_skill_pack_is_merged_into_agent_prompt_context(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            overlay_root = runtime_dir / "skills" / "macro-pack" / "agents" / "market_reasoning"
            (overlay_root / "references").mkdir(parents=True)
            (overlay_root / "skill.md").write_text(
                "\n".join(
                    [
                        "---",
                        "agent_id: market_reasoning",
                        "version: 2",
                        "---",
                        "",
                        "Overlay skill body for market reasoning.",
                    ]
                ),
                encoding="utf-8",
            )
            (overlay_root / "references" / "overlay_map.md").write_text(
                "Overlay transmission reference.",
                encoding="utf-8",
            )
            loader = AgentSkillLoader(workspace_root=runtime_dir)
            spec = loader.load(
                "market_reasoning",
                ROOT / "src" / "fitech_agent" / "agents" / "market_reasoning" / "skill.md",
                extra_roots=["skills"],
            )
            prompt_context = spec.prompt_context()
            self.assertIn("Overlay skill body for market reasoning.", prompt_context)
            self.assertIn("Overlay transmission reference.", prompt_context)
            self.assertGreaterEqual(len(spec.source_paths), 2)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
