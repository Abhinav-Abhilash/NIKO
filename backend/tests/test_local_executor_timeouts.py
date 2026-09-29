import asyncio
import sys
from typing import Any

import pytest

from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult
from backend.app.skills.executor import LocalExecutor


class FastSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="fast_skill",
            description="Returns fast",
            timeout_seconds=2,
        )

    async def execute(self, _arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        return SkillResult(success=True, data={"result": "ok"})


class HangingSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="hanging_skill",
            description="Sleeps longer than timeout",
            timeout_seconds=1,
        )

    async def execute(self, _arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        await asyncio.sleep(5)
        return SkillResult(success=True, data={"result": "too_late"})


class ErrorSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="error_skill",
            description="Raises error",
            timeout_seconds=2,
        )

    async def execute(self, _arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        raise RuntimeError("Something exploded")


@pytest.mark.asyncio
async def test_executor_fast_skill_success() -> None:
    executor = LocalExecutor()
    ctx = SkillContext(request_id="req_fast", provenance="direct")

    result = await executor.execute(FastSkill(), {}, ctx)
    assert result.success is True
    assert result.data == {"result": "ok"}
    assert result.execution_time_ms >= 0.0


@pytest.mark.asyncio
async def test_executor_hanging_skill_times_out() -> None:
    executor = LocalExecutor()
    ctx = SkillContext(request_id="req_hang", provenance="direct")

    result = await executor.execute(HangingSkill(), {}, ctx)
    assert result.success is False
    assert "timed out after 1" in (result.error or "")
    assert result.execution_time_ms >= 800.0  # Approx ~1000ms


@pytest.mark.asyncio
async def test_executor_error_handling() -> None:
    executor = LocalExecutor()
    ctx = SkillContext(request_id="req_err", provenance="direct")

    result = await executor.execute(ErrorSkill(), {}, ctx)
    assert result.success is False
    assert "Something exploded" in (result.error or "")


@pytest.mark.asyncio
async def test_run_subprocess_success() -> None:
    code, stdout, stderr = await LocalExecutor.run_subprocess(
        [sys.executable, "-c", "import sys; sys.stdout.write('niko-alive'); sys.stderr.write('no-err')"],
        timeout=5.0,
    )
    assert code == 0
    assert stdout == "niko-alive"
    assert stderr == "no-err"


@pytest.mark.asyncio
async def test_run_subprocess_timeout_and_kill() -> None:
    with pytest.raises(TimeoutError, match="timed out after 0.2s"):
        await LocalExecutor.run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.2,
        )


@pytest.mark.asyncio
async def test_run_in_thread() -> None:
    def sync_compute(a: int, b: int) -> int:
        return a * b

    res = await LocalExecutor.run_in_thread(sync_compute, 6, 7)
    assert res == 42
