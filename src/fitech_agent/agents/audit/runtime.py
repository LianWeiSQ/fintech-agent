from __future__ import annotations

from ..base import AgentDescriptor, AgentSkillSpec
from . import prompts


class AuditRuntime:
    def __init__(self, descriptor: AgentDescriptor, skill: AgentSkillSpec) -> None:
        self.descriptor = descriptor
        self.skill = skill

    def system_prompt(self) -> str:
        return prompts.build_system_prompt(self.skill.prompt_context())
