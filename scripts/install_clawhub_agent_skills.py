from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path
import tomllib

RATE_LIMIT_RE = re.compile(r"retry in (\d+)([smh])", re.IGNORECASE)
RATE_LIMIT_MARKER = "Rate limit exceeded"
SUSPICIOUS_MARKER = "Use --force to install suspicious skills in non-interactive mode"


def load_manifest(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def resolve_slugs(manifest: dict, agents: list[str]) -> list[str]:
    declared_agents = manifest.get("agents", {})
    if not agents:
        agents = list(declared_agents.keys())

    slugs: list[str] = []
    seen: set[str] = set()
    for agent_id in agents:
        agent = declared_agents.get(agent_id)
        if not agent:
            raise SystemExit(f"Unknown agent: {agent_id}")
        for slug in agent.get("skills", []):
            if slug not in seen:
                seen.add(slug)
                slugs.append(slug)
    return slugs


def build_command(wrapper: Path, slug: str, force_suspicious: bool) -> list[str]:
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(wrapper),
        "--no-input",
        "install",
    ]
    if force_suspicious:
        command.append("--force")
    command.append(slug)
    return command


def infer_retry_delay(output: str, fallback_seconds: int) -> int:
    delays: list[int] = []
    for raw_value, unit in RATE_LIMIT_RE.findall(output):
        value = int(raw_value)
        unit = unit.lower()
        if unit == "m":
            value *= 60
        elif unit == "h":
            value *= 3600
        delays.append(value)
    if not delays:
        return fallback_seconds
    return max(fallback_seconds, max(delays) + 2)


def emit_output(result: subprocess.CompletedProcess[str]) -> str:
    chunks: list[str] = []
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        chunks.append(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
        chunks.append(result.stderr)
    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the ClawHub skill packs selected for the 5 core agents."
    )
    parser.add_argument(
        "--manifest",
        default="skills/clawhub_selection.toml",
        help="Path to the selection manifest.",
    )
    parser.add_argument(
        "--agent",
        action="append",
        dest="agents",
        default=[],
        help="Install only the skills selected for one agent. Repeatable.",
    )
    parser.add_argument(
        "--force-suspicious",
        action="store_true",
        help="Pass --force to all selected ClawHub installs.",
    )
    parser.add_argument(
        "--force-slug",
        action="append",
        default=[],
        help="Pass --force only for the specified slug. Repeatable.",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=3,
        help="Retries per slug after the initial attempt.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=10,
        help="Fallback seconds to wait before retrying a failed install.",
    )
    parser.add_argument(
        "--inter-install-sleep-seconds",
        type=int,
        default=3,
        help="Seconds to wait between successful installs.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    repo_root = manifest_path.parent.parent
    wrapper = repo_root / "scripts" / "clawhub.ps1"
    install_root = repo_root / "skills"

    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    if not wrapper.exists():
        raise SystemExit(f"ClawHub wrapper not found: {wrapper}")

    manifest = load_manifest(manifest_path)
    slugs = resolve_slugs(manifest, args.agents)
    forced_slugs = set(args.force_slug)

    print(f"Install root: {install_root}")
    print(f"Selected slugs ({len(slugs)}): {', '.join(slugs)}")

    failed: list[str] = []
    suspicious_blocked: list[str] = []

    for index, slug in enumerate(slugs):
        destination = install_root / slug
        if destination.exists():
            print(f"[skip] {slug} -> {destination}")
            continue

        attempts = args.retry + 1
        force_this_slug = args.force_suspicious or slug in forced_slugs
        for attempt in range(1, attempts + 1):
            print(f"[install {attempt}/{attempts}] {slug}")
            result = subprocess.run(
                build_command(wrapper, slug, force_this_slug),
                cwd=repo_root,
                text=True,
                capture_output=True,
            )
            output = emit_output(result)
            if result.returncode == 0 and destination.exists():
                print(f"[ok] {slug} -> {destination}")
                if index < len(slugs) - 1 and args.inter_install_sleep_seconds > 0:
                    time.sleep(args.inter_install_sleep_seconds)
                break

            if SUSPICIOUS_MARKER in output and not force_this_slug:
                print(
                    f"[blocked] {slug} is marked suspicious. Review it, then rerun with --force-slug {slug}."
                )
                suspicious_blocked.append(slug)
                break

            if attempt < attempts:
                delay = infer_retry_delay(output, args.sleep_seconds)
                if RATE_LIMIT_MARKER in output:
                    print(f"[rate-limit] {slug}; waiting {delay}s before retry")
                else:
                    print(f"[retry] {slug} in {delay}s")
                time.sleep(delay)
            else:
                failed.append(slug)

    if suspicious_blocked:
        print("Suspicious packs awaiting manual review:", ", ".join(suspicious_blocked))
    if failed:
        print("Failed installs:", ", ".join(failed))
        return 1

    print("All requested ClawHub skill packs are installed or intentionally skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
