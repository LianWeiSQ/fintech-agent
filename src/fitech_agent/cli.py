from __future__ import annotations

import argparse
from pathlib import Path

from .config import default_config_path, load_config, load_dotenv
from .evaluation import ForecastEvaluator, load_price_observations
from .pipeline import NewsPipeline
from .storage import SQLiteStorage


def build_parser(default_config: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Fitech Agent pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Initialize the SQLite store.")
    init_db.add_argument("--config", type=Path, default=default_config)

    run_daily = subparsers.add_parser("run-daily", help="Run the daily briefing pipeline.")
    run_daily.add_argument("--config", type=Path, default=default_config)
    run_daily.add_argument("--scheduled-for", type=str, default=None)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a stored run against observations.")
    evaluate.add_argument("--config", type=Path, default=default_config)
    evaluate.add_argument("--run-id", type=int, required=True)
    evaluate.add_argument("--prices-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser(default_config_path())
    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "init-db":
        SQLiteStorage(config.database_path).initialize()
        print(f"Initialized database at {config.database_path}")
        return 0

    if args.command == "run-daily":
        pipeline = NewsPipeline(config)
        result = pipeline.run(scheduled_for=args.scheduled_for)
        print(f"Run ID: {result['run_id']}")
        print(f"Markdown: {result['markdown_path']}")
        print(f"PDF: {result['pdf_path'] or 'not generated'}")
        return 0

    if args.command == "evaluate":
        storage = SQLiteStorage(config.database_path)
        assessments = storage.load_assessments(args.run_id)
        observations = load_price_observations(args.prices_file)
        outcomes = ForecastEvaluator().evaluate(args.run_id, assessments, observations)
        storage.record_outcomes(args.run_id, outcomes)
        print(f"Recorded {len(outcomes)} outcome rows for run {args.run_id}")
        return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
