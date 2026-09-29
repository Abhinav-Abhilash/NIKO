from typing import Any

from backend.app.core.exceptions import NotFoundError
from backend.app.core.logging import get_logger
from backend.app.skills.base import BaseSkill, SkillManifest

logger = get_logger("skill_registry")


class SkillRegistry:
    """Central registry for discovering, inspecting, and retrieving executable skills."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a skill implementation. Overwrites any existing skill with the same name."""
        name = skill.manifest.name
        self._skills[name] = skill
        logger.info(
            "Registered skill",
            name=name,
            tier=skill.manifest.default_tier,
            autonomy=skill.manifest.default_autonomy,
        )

    def get(self, name: str) -> BaseSkill:
        """Retrieve a registered skill by name. Raises NotFoundError if unregistered."""
        if name not in self._skills:
            raise NotFoundError(f"Skill '{name}' is not registered.")
        return self._skills[name]

    def has(self, name: str) -> bool:
        """Check if a skill is registered."""
        return name in self._skills

    def list_manifests(self) -> list[SkillManifest]:
        """Return manifests for all registered skills."""
        return [skill.manifest for skill in self._skills.values()]

    def list_skills(self) -> list[BaseSkill]:
        """Return all registered skill instances."""
        return list(self._skills.values())

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Export registered skill manifests as JSON schema function definitions
        compatible with LLM function calling (Gemini, Groq, OpenRouter).
        """
        tools = []
        for manifest in self.list_manifests():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": manifest.name,
                        "description": manifest.description,
                        "parameters": manifest.parameters_schema
                        or {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    },
                }
            )
        return tools


# Global singleton registry instance
_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
