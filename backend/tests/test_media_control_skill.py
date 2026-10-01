import pytest

from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.media_control_skill import MediaControlSkill


@pytest.mark.asyncio
async def test_media_control_manifest() -> None:
    skill = MediaControlSkill()
    manifest = skill.manifest

    assert manifest.name == "media_control"
    assert manifest.default_tier == "SAFE"
    assert "action" in manifest.parameters_schema["properties"]


@pytest.mark.asyncio
async def test_media_control_valid_actions() -> None:
    skill = MediaControlSkill()
    ctx = SkillContext(request_id="test_media_1", user_id="test_user", provenance="direct")

    actions = ["play_pause", "next", "previous", "mute", "volume_up", "volume_down"]
    for act in actions:
        res = await skill.execute({"action": act}, ctx)
        assert res.success is True
        assert res.data["action"] == act


@pytest.mark.asyncio
async def test_media_control_invalid_action() -> None:
    skill = MediaControlSkill()
    ctx = SkillContext(request_id="test_media_2", user_id="test_user", provenance="direct")

    res = await skill.execute({"action": "unknown_action"}, ctx)
    assert res.success is False
    assert "Unsupported media action" in res.error
