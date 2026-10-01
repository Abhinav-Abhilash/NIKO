import pytest

from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.window_control_skill import WindowControlSkill


@pytest.mark.asyncio
async def test_window_control_manifest() -> None:
    skill = WindowControlSkill()
    manifest = skill.manifest

    assert manifest.name == "window_control"
    assert manifest.default_tier == "CONFIRM"
    assert "action" in manifest.parameters_schema["properties"]


@pytest.mark.asyncio
async def test_window_control_list() -> None:
    skill = WindowControlSkill()
    ctx = SkillContext(request_id="test_win_1", user_id="test_user", provenance="direct")

    res = await skill.execute({"action": "list"}, ctx)
    assert res.success is True
    assert "windows" in res.data
    assert isinstance(res.data["windows"], list)


@pytest.mark.asyncio
async def test_window_control_inspect() -> None:
    skill = WindowControlSkill()
    ctx = SkillContext(request_id="test_win_inspect", user_id="test_user", provenance="direct")

    res = await skill.execute({"action": "inspect"}, ctx)
    assert res.success is True
    assert "active_window" in res.data
    assert "cursor" in res.data
    assert "visible_windows" in res.data
    assert "count" in res.data
    assert isinstance(res.data["cursor"], dict)
    assert "x" in res.data["cursor"]
    assert "y" in res.data["cursor"]


@pytest.mark.asyncio
async def test_window_control_focus_nonexistent() -> None:
    skill = WindowControlSkill()
    ctx = SkillContext(request_id="test_win_2", user_id="test_user", provenance="direct")

    res = await skill.execute({"action": "focus", "title": "NonExistentWindowTitle_9999"}, ctx)
    assert res.success is False
    assert res.error is not None and "No active window matching" in res.error


@pytest.mark.asyncio
async def test_window_control_invalid_action() -> None:
    skill = WindowControlSkill()
    ctx = SkillContext(request_id="test_win_3", user_id="test_user", provenance="direct")

    res = await skill.execute({"action": "destroy"}, ctx)
    assert res.success is False
    assert res.error is not None and "Unsupported window action" in res.error
