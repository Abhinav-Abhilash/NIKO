import pytest

from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.clipboard_skill import ClipboardSkill, get_clipboard_text, set_clipboard_text


@pytest.mark.asyncio
async def test_clipboard_skill_manifest() -> None:
    skill = ClipboardSkill()
    manifest = skill.manifest

    assert manifest.name == "clipboard"
    assert manifest.default_tier == "CONFIRM"
    assert "action" in manifest.parameters_schema["properties"]


@pytest.mark.asyncio
async def test_clipboard_write_and_read() -> None:
    skill = ClipboardSkill()
    ctx = SkillContext(request_id="test_clip_1", user_id="test_user", provenance="direct")

    test_text = "NIKO AI Test Clipboard Payload 12345"

    # Write action
    write_res = await skill.execute({"action": "write", "text": test_text}, ctx)
    assert write_res.success is True
    assert write_res.data["action"] == "write"

    # Read action
    read_res = await skill.execute({"action": "read"}, ctx)
    assert read_res.success is True
    assert read_res.data["action"] == "read"
    assert read_res.data["content"] == test_text


@pytest.mark.asyncio
async def test_clipboard_invalid_action() -> None:
    skill = ClipboardSkill()
    ctx = SkillContext(request_id="test_clip_2", user_id="test_user", provenance="direct")

    res = await skill.execute({"action": "invalid_op"}, ctx)
    assert res.success is False
    assert "Unsupported clipboard action" in res.error
