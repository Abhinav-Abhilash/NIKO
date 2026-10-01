import pytest

from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.disk_cleaner_skill import DiskCleanerSkill
from backend.app.skills.builtin.file_finder_skill import FileFinderSkill


@pytest.mark.asyncio
async def test_file_finder_manifest_and_search() -> None:
    skill = FileFinderSkill()
    manifest = skill.manifest

    assert manifest.name == "file_finder"
    assert manifest.default_tier == "SAFE"

    ctx = SkillContext(request_id="test_ff_1", user_id="user_123", provenance="direct")
    res = await skill.execute({"action": "search_name", "query": "ROADMAP"}, ctx)
    assert res.success is True
    assert "files" in res.data


@pytest.mark.asyncio
async def test_file_finder_open_unapproved_path() -> None:
    skill = FileFinderSkill()
    ctx = SkillContext(request_id="test_ff_2", user_id="user_123", provenance="direct")

    res = await skill.execute({"action": "open", "file_path": "C:\\Windows\\System32\\cmd.exe"}, ctx)
    assert res.success is False
    assert res.error is not None and "Access denied" in res.error


@pytest.mark.asyncio
async def test_disk_cleaner_report() -> None:
    skill = DiskCleanerSkill()
    manifest = skill.manifest

    assert manifest.name == "disk_cleaner"
    assert manifest.default_tier == "CONFIRM"

    ctx = SkillContext(request_id="test_dc_1", user_id="user_123", provenance="direct")
    res = await skill.execute({"action": "report"}, ctx)
    assert res.success is True
    assert "total_free_gb" in res.data
    assert "reclaimable_mb" in res.data
