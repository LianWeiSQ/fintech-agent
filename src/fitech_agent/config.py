from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .source_catalog import infer_source_tier


@dataclass(slots=True)
class SourceDefinition:
    name: str
    kind: str
    endpoint: str
    language: str = "mixed"
    tier: str = "unknown"
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AuditSettings:
    min_verified_score: float = 0.65
    min_publish_confidence: float = 0.55


@dataclass(slots=True)
class ModelRoute:
    provider: str = ""
    model: str = ""
    temperature: float = 0.1
    max_output_tokens: int = 900
    base_url: str = ""
    api_key_env: str = ""


@dataclass(slots=True)
class AppConfig:
    timezone: str = "Asia/Shanghai"
    report_time: str = "07:00"
    report_language: str = "zh-CN"
    database_path: str = "artifacts/fitech_agent.db"
    report_dir: str = "artifacts/reports"
    sources: list[SourceDefinition] = field(default_factory=list)
    audit: AuditSettings = field(default_factory=AuditSettings)
    model_route: ModelRoute = field(default_factory=ModelRoute)


def load_dotenv(path: str | Path = ".env") -> Path | None:
    env_path = Path(path)
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return env_path


def default_config_path() -> Path:
    return Path(os.environ.get("FITECH_AGENT_CONFIG", "config/example.toml"))


def load_config(path: str | Path | None = None) -> AppConfig:
    load_dotenv()
    if path is None:
        return AppConfig()

    config_path = Path(path)
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    sources = []
    for item in payload.get("sources", []):
        source_payload = dict(item)
        source_payload["tier"] = infer_source_tier(
            source_payload.get("name", ""),
            source_payload.get("tier", ""),
        )
        sources.append(SourceDefinition(**source_payload))
    audit = AuditSettings(**payload.get("audit", {}))
    model_route = ModelRoute(**payload.get("model_route", {}))
    return AppConfig(
        timezone=payload.get("timezone", "Asia/Shanghai"),
        report_time=payload.get("report_time", "07:00"),
        report_language=payload.get("report_language", "zh-CN"),
        database_path=payload.get("database_path", "artifacts/fitech_agent.db"),
        report_dir=payload.get("report_dir", "artifacts/reports"),
        sources=sources,
        audit=audit,
        model_route=model_route,
    )
