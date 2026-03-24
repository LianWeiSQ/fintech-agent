from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.config import default_config_path, load_config, load_dotenv
from fitech_agent.llm import LiteLLMClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test a Codex-compatible Responses gateway."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="Project config to load before applying CLI overrides.",
    )
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--backend", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--api-key-env", type=str, default=None)
    parser.add_argument(
        "--reasoning-effort",
        type=str,
        default=None,
        choices=("minimal", "low", "medium", "high", "xhigh"),
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default="You are a connectivity test. Reply with exactly MODEL_OK.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Reply with exactly MODEL_OK",
    )
    parser.add_argument(
        "--expect",
        type=str,
        default="MODEL_OK",
        help="Exact response expected from the model.",
    )
    return parser


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()

    config_path = args.config if args.config and args.config.exists() else None
    config = load_config(config_path)
    route = config.resolve_model_route()

    if args.provider is not None:
        route.provider = args.provider
    if args.backend is not None:
        route.backend = args.backend
    if args.model is not None:
        route.model = args.model
    if args.base_url is not None:
        route.base_url = args.base_url
    if args.api_key_env is not None:
        route.api_key_env = args.api_key_env
    if args.reasoning_effort is not None:
        route.reasoning_effort = args.reasoning_effort

    client = LiteLLMClient(route)
    snapshot = client.snapshot()
    result = client.complete_text_result(args.system_prompt, args.prompt)

    print(
        json.dumps(
            {
                "provider": snapshot.get("provider"),
                "backend": snapshot.get("backend"),
                "resolved_model": snapshot.get("resolved_model"),
                "resolved_base_url": snapshot.get("resolved_base_url"),
                "resolved_reasoning_effort": snapshot.get("resolved_reasoning_effort"),
                "api_key_configured": snapshot.get("api_key_configured"),
                "availability_error": snapshot.get("availability_error"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "ok": bool(result.text),
                "backend": result.backend,
                "model": result.model,
                "base_url": result.base_url,
                "error": result.error,
                "text": result.text,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if not result.text:
        return 1
    if args.expect and result.text.strip() != args.expect.strip():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "unexpected_response",
                    "expected": args.expect,
                    "actual": result.text,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
