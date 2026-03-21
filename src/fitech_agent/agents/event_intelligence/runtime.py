from __future__ import annotations

from ..base import AgentDescriptor, AgentSkillSpec
from . import prompts


class EventIntelligenceRuntime:
    def __init__(self, descriptor: AgentDescriptor, skill: AgentSkillSpec) -> None:
        self.descriptor = descriptor
        self.skill = skill

    def system_prompt(self, instruction: str | None = None) -> str:
        parts = [prompts.build_system_prompt(self.skill.prompt_context())]
        if instruction:
            parts.append(instruction)
        return "\n\n".join(parts)
