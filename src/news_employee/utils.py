from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=json_default, indent=2)


def json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def stable_id(*parts: str, size: int = 12) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:size]


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def iso_day(iso_timestamp: str) -> str:
    return iso_timestamp[:10] if iso_timestamp else ""


def within_days(reference_iso: str, days: int) -> list[str]:
    anchor = datetime.fromisoformat(reference_iso.replace("Z", "+00:00"))
    return [
        (anchor + timedelta(days=offset)).date().isoformat()
        for offset in range(days + 1)
    ]

