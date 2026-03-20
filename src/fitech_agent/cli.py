from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import default_config_path, load_config, load_dotenv
from .evaluation import ForecastEvaluator, load_price_observations
from .models import ResearchRunRequest
from .pipeline import ResearchPipeline
from .storage import SQLiteStorage


def _add_run_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_mode: bool,
    include_legacy_scheduled_for: bool = False,
) -> None:
    parser.add_argument("--config", type=Path, default=None)
    if include_mode:
        parser.add_argument(
            "--mode",
            choices=("full-report", "collect-only"),
            default=None,
            help="Run the full research flow or collect-only mode.",
        )
    parser.add_argument("--triggered-at", type=str, default=None)
    if include_legacy_scheduled_for:
        parser.add_argument("--scheduled-for", type=str, default=None)
    parser.add_argument("--lookback-hours", type=int, default=None)
    parser.add_argument("--window-start", type=str, default=None)
    parser.add_argument("--window-end", type=str, default=None)
    parser.add_argument("--scope", action="append", default=None)
    parser.add_argument("--source", action="append", default=None)


def build_parser(default_config: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Fitech Agent pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Initialize the SQLite store.")
    init_db.add_argument("--config", type=Path, default=default_config)

    run_command = subparsers.add_parser("run", help="Run the manual research pipeline.")
    _add_run_arguments(run_command, include_mode=True)

    run_daily = subparsers.add_parser(
        "run-daily",
        help="Deprecated alias for `run --mode full-report`.",
    )
    _add_run_arguments(
        run_daily,
        include_mode=False,
        include_legacy_scheduled_for=True,
    )

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a stored run against observations.")
    evaluate.add_argument("--config", type=Path, default=default_config)
    evaluate.add_argument("--run-id", type=int, required=True)
    evaluate.add_argument("--prices-file", type=Path, required=True)

    serve = subparsers.add_parser("serve", help="Start the local dashboard.")
    serve.add_argument("--config", type=Path, default=default_config)
    serve.add_argument("--host", type=str, default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8010)
    return parser


def _resolve_config_path(args: argparse.Namespace, default_config: Path) -> Path:
    return args.config or default_config


def _build_run_request(args: argparse.Namespace) -> ResearchRunRequest:
    if args.command == "run-daily":
        triggered_at = args.triggered_at or args.scheduled_for
        mode = "full_report"
    else:
        triggered_at = args.triggered_at
        mode = args.mode.replace("-", "_") if args.mode else None
    return ResearchRunRequest(
        mode=mode,
        triggered_at=triggered_at,
        lookback_hours=args.lookback_hours,
        window_start=args.window_start,
        window_end=args.window_end,
        scopes=list(args.scope or []),
        sources=list(args.source or []),
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    default_config = default_config_path()
    parser = build_parser(default_config)
    args = parser.parse_args(argv)

    if args.command == "serve":
        from .webapp import create_server

        server = create_server(
            config_path=_resolve_config_path(args, default_config),
            host=args.host,
            port=args.port,
        )
        print(f"Dashboard: http://{args.host}:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping dashboard...")
        finally:
            server.server_close()
        return 0

    config = load_config(_resolve_config_path(args, default_config))

    if args.command == "init-db":
        SQLiteStorage(config.database_path).initialize()
        print(f"Initialized database at {config.database_path}")
        return 0

    if args.command in {"run", "run-daily"}:
        if args.command == "run-daily":
            print(
                "Deprecation warning: `run-daily` will be removed in a future version; "
                "use `run --mode full-report` instead.",
                file=sys.stderr,
            )
        pipeline = ResearchPipeline(config)
        try:
            result = pipeline.run(_build_run_request(args))
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Run ID: {result.run_id}")
        print(f"Mode: {result.mode.replace('_', '-')}")
        print(f"Triggered At: {result.triggered_at}")
        print(f"Window: {result.window.start} -> {result.window.end}")
        print(f"Collected Items: {len(result.raw_items)}")
        print(f"Sources: {', '.join(result.sources)}")
        if result.markdown_path is not None:
            print(f"Markdown: {result.markdown_path}")
            print(f"PDF: {result.pdf_path or 'not generated'}")
        else:
            print("Markdown: not generated")
            print("PDF: not generated")
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
