from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar

from ..config import AppConfig
from ..llm import LiteLLMClient
from ..models import NewsWindow
from ..storage import SQLiteStorage

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(slots=True)
class AgentDescriptor:
    agent_id: str
    display_name: str
    skill_path: Path
    default_route_name: str
    substages: tuple[str, ...] = ()


@dataclass(slots=True)
class AgentSkillSpec:
    agent_id: str
    path: Path
    exists: bool
    metadata: dict[str, object] = field(default_factory=dict)
    body: str = ""
    source_paths: list[Path] = field(default_factory=list)
    resources: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def prompt_context(self) -> str:
        parts: list[str] = []
        if self.body:
            parts.append(self.body.strip())
        for category in ("references", "checklists", "templates", "examples"):
            items = self.resources.get(category, [])
            if not items:
                continue
            rendered = [f"[{item['name']}]\n{item['content'].strip()}" for item in items if item.get("content")]
            if rendered:
                parts.append(f"{category.title()}:\n" + "\n\n".join(rendered))
        return "\n\n".join(part for part in parts if part).strip()


@dataclass(slots=True)
class AgentRuntimeContext:
    run_id: int
    mode: str
    triggered_at: str
    window: NewsWindow
    scopes: list[str]
    sources: list[str]
    config: AppConfig
    storage: SQLiteStorage
    llm_client: LiteLLMClient
    descriptor: AgentDescriptor
    skill: AgentSkillSpec


class BaseResearchAgent(ABC, Generic[InputT, OutputT]):
    descriptor: AgentDescriptor

    def run(self, context: AgentRuntimeContext, payload: InputT) -> OutputT:
        return self.execute(context, payload)

    @abstractmethod
    def execute(self, context: AgentRuntimeContext, payload: InputT) -> OutputT:
        raise NotImplementedError
