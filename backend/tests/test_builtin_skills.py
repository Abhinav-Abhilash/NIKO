from typing import Any

import pytest

from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.datetime_skill import DateTimeSkill
from backend.app.skills.builtin.system_stats_skill import SystemStatsSkill


@pytest.mark.asyncio
async def test_datetime_skill_execution() -> None:
    skill = DateTimeSkill()
    assert skill.manifest.name == "datetime"
    assert skill.manifest.default_tier == "SAFE"
    assert skill.manifest.default_autonomy == "auto"

    ctx = SkillContext(request_id="req_dt", provenance="direct")
    result = await skill.execute({}, ctx)

    assert result.success is True
    data: dict[str, Any] = result.data
    assert "iso_local" in data
    assert "iso_utc" in data
    assert "date" in data
    assert "time" in data
    assert "day_of_week" in data
    assert "epoch_timestamp" in data


@pytest.mark.asyncio
async def test_datetime_skill_with_format() -> None:
    skill = DateTimeSkill()
    ctx = SkillContext(request_id="req_dt_fmt", provenance="direct")
    result = await skill.execute({"format": "%Y/%m/%d"}, ctx)

    assert result.success is True
    assert "/" in result.data["formatted"]


@pytest.mark.asyncio
async def test_system_stats_skill_execution() -> None:
    skill = SystemStatsSkill()
    assert skill.manifest.name == "system_stats"
    assert skill.manifest.default_tier == "SAFE"
    assert skill.manifest.default_autonomy == "auto"

    ctx = SkillContext(request_id="req_stats", provenance="direct")
    result = await skill.execute({}, ctx)

    assert result.success is True
    data: dict[str, Any] = result.data
    assert "cpu" in data
    assert "percent" in data["cpu"]
    assert "ram" in data
    assert "percent" in data["ram"]
    assert "total_mb" in data["ram"]
    assert "disk" in data
    assert "percent" in data["disk"]
    assert "battery" in data


@pytest.mark.asyncio
async def test_system_stats_skill_with_detail() -> None:
    skill = SystemStatsSkill()
    ctx = SkillContext(request_id="req_stats_det", provenance="direct")
    result = await skill.execute({"detail": True}, ctx)

    assert result.success is True
    data: dict[str, Any] = result.data
    assert "per_cpu_percent" in data["cpu"]
