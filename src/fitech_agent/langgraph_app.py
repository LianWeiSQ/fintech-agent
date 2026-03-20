from __future__ import annotations

from .config import default_config_path, load_config, load_dotenv
from .pipeline import NewsPipeline


load_dotenv()
config_path = default_config_path()
graph = NewsPipeline(load_config(config_path if config_path.exists() else None)).graph
