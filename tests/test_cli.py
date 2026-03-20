from __future__ import annotations

import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_tests_runtime"
TMP_ROOT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.cli import main


def _path_value(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


class CliTests(unittest.TestCase):
    def _make_runtime_dir(self) -> Path:
        path = TMP_ROOT / uuid4().hex
        path.mkdir(parents=True, exist_ok=False)
        return path

    def _write_config(self, tmpdir: Path) -> Path:
        config_path = tmpdir / "config.toml"
        sample_path = ROOT / "examples" / "sample_news.json"
        config_path.write_text(
            "\n".join(
                [
                    'timezone = "Asia/Shanghai"',
                    'report_language = "zh-CN"',
                    f'database_path = "{_path_value(tmpdir / "fitech_agent.db")}"',
                    f'report_dir = "{_path_value(tmpdir / "reports")}"',
                    "",
                    "[audit]",
                    "min_verified_score = 0.65",
                    "min_publish_confidence = 0.55",
                    "",
                    "[model_route]",
                    'provider = ""',
                    'model = ""',
                    "temperature = 0.1",
                    "max_output_tokens = 900",
                    'base_url = ""',
                    'api_key_env = ""',
                    "",
                    "[run_defaults]",
                    'mode = "full_report"',
                    "lookback_hours = 18",
                    "",
                    "[[sources]]",
                    'name = "bootstrap_sample"',
                    'kind = "file"',
                    f'endpoint = "{_path_value(sample_path)}"',
                    'language = "mixed"',
                    'tier = "tier1_media"',
                    "enabled = true",
                    'tags = ["bootstrap", "macro"]',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def test_run_collect_only_cli(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config_path = self._write_config(runtime_dir)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "run",
                        "--config",
                        str(config_path),
                        "--mode",
                        "collect-only",
                        "--triggered-at",
                        "2026-03-20T07:00:00+08:00",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("Mode: collect-only", stdout.getvalue())
            self.assertIn("Markdown: not generated", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_run_daily_alias_prints_deprecation_warning(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config_path = self._write_config(runtime_dir)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "run-daily",
                        "--config",
                        str(config_path),
                        "--scheduled-for",
                        "2026-03-20T07:00:00+08:00",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("Mode: full-report", stdout.getvalue())
            self.assertIn("Deprecation warning", stderr.getvalue())
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    def test_cli_rejects_single_window_bound(self) -> None:
        runtime_dir = self._make_runtime_dir()
        try:
            config_path = self._write_config(runtime_dir)
            with self.assertRaises(SystemExit) as exc:
                main(
                    [
                        "run",
                        "--config",
                        str(config_path),
                        "--window-start",
                        "2026-03-19T00:00:00+08:00",
                    ]
                )
            self.assertEqual(exc.exception.code, 2)
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
