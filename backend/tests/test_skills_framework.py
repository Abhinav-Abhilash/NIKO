from typing import Any

import pytest

from backend.app.core.exceptions import NotFoundError
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult
from backend.app.skills.registry import SkillRegistry


class DummyEchoSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="dummy_echo",
            description="Echoes input for testing",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        return SkillResult(success=True, data={"echo": arguments.get("message")})


def test_manifest_validation() -> None:
    manifest = DummyEchoSkill().manifest
    assert manifest.name == "dummy_echo"
    assert manifest.default_tier == "SAFE"
    assert manifest.default_autonomy == "auto"
    assert manifest.timeout_seconds == 5
    assert "message" in manifest.parameters_schema["properties"]


def test_registry_registration_and_lookup() -> None:
    reg = SkillRegistry()
    skill = DummyEchoSkill()
    reg.register(skill)

    assert reg.has("dummy_echo")
    assert reg.get("dummy_echo") is skill
    assert len(reg.list_manifests()) == 1
    assert reg.list_manifests()[0].name == "dummy_echo"


def test_registry_overwrite_registration() -> None:
    reg = SkillRegistry()
    skill1 = DummyEchoSkill()
    skill2 = DummyEchoSkill()
    reg.register(skill1)
    reg.register(skill2)

    assert reg.get("dummy_echo") is skill2


def test_registry_nonexistent_lookup_raises() -> None:
    reg = SkillRegistry()
    with pytest.raises(NotFoundError, match="not registered"):
        reg.get("nonexistent_skill")


def test_registry_get_tool_definitions() -> None:
    reg = SkillRegistry()
    reg.register(DummyEchoSkill())

    tools = reg.get_tool_definitions()
    assert len(tools) == 1
    tool = tools[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "dummy_echo"
    assert tool["function"]["description"] == "Echoes input for testing"
    assert "message" in tool["function"]["parameters"]["properties"]
