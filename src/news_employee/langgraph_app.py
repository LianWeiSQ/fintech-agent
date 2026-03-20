from __future__ import annotations

import os
from pathlib import Path

from .config import load_config
from .pipeline import NewsPipeline


config_path = Path(os.environ.get("NEWS_EMPLOYEE_CONFIG", "config/example.toml"))
graph = NewsPipeline(load_config(config_path if config_path.exists() else None)).graph
