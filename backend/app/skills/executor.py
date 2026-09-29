import asyncio
import functools
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from backend.app.core.logging import get_logger
from backend.app.skills.base import BaseSkill, SkillContext, SkillExecutor, SkillResult

logger = get_logger("local_executor")
T = TypeVar("T")

# Dedicated bounded worker thread pool for synchronous PC automation tasks (e.g., COM, psutil)
_DEFAULT_MAX_WORKERS = 4
_worker_pool: ThreadPoolExecutor | None = None


def get_worker_thread_pool(max_workers: int = _DEFAULT_MAX_WORKERS) -> ThreadPoolExecutor:
    """Return singleton bounded ThreadPoolExecutor, preventing unbounded OS thread allocation."""
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="niko-worker",
        )
    return _worker_pool


def shutdown_worker_thread_pool() -> None:
    """Cleanly shut down the bounded worker thread pool."""
    global _worker_pool
    if _worker_pool is not None:
        _worker_pool.shutdown(wait=False)
        _worker_pool = None


class LocalExecutor(SkillExecutor):
    """
    Local PC automation executor.
    Enforces timeout barriers, captures execution metrics, and provides safe
    subprocess and thread-pool execution abstractions for PC automation.
    """

    async def execute(
        self,
        skill: BaseSkill,
        arguments: dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Execute a skill within a strict timeout barrier and measure latency."""
        start_time = time.perf_counter()
        timeout = float(skill.manifest.timeout_seconds)

        try:
            logger.info(
                "Executing skill",
                skill=skill.manifest.name,
                request_id=context.request_id,
                timeout=timeout,
            )
            result = await asyncio.wait_for(
                skill.execute(arguments, context),
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            result.execution_time_ms = round(elapsed_ms, 2)
            return result

        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = f"Skill '{skill.manifest.name}' execution timed out after {timeout} seconds."
            logger.warning(
                "Skill execution timed out",
                skill=skill.manifest.name,
                timeout=timeout,
                request_id=context.request_id,
            )
            return SkillResult(
                success=False,
                error=error_msg,
                execution_time_ms=round(elapsed_ms, 2),
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                "Skill execution failed with unhandled exception",
                skill=skill.manifest.name,
                request_id=context.request_id,
                exc_info=exc,
            )
            return SkillResult(
                success=False,
                error=str(exc) or "Internal execution failure.",
                execution_time_ms=round(elapsed_ms, 2),
            )

    @staticmethod
    async def run_subprocess(
        cmd: list[str],
        timeout: float = 15.0,
        input_data: str | None = None,
    ) -> tuple[int, str, str]:
        """
        Execute an external system command via subprocess with argument list isolation (no shell=True).
        Enforces process-level kill on timeout.
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            input_bytes = input_data.encode("utf-8") if input_data else None
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=input_bytes),
                timeout=timeout,
            )
            return (
                proc.returncode if proc.returncode is not None else -1,
                stdout_bytes.decode("utf-8", errors="replace"),
                stderr_bytes.decode("utf-8", errors="replace"),
            )
        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(f"Command '{cmd[0]}' timed out after {timeout}s and was terminated.") from None

    @classmethod
    async def run_in_thread(cls, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run blocking or synchronous Windows calls in a dedicated bounded worker thread pool."""
        loop = asyncio.get_running_loop()
        pool = get_worker_thread_pool()
        if kwargs:
            call = functools.partial(func, *args, **kwargs)
            return await loop.run_in_executor(pool, call)
        return await loop.run_in_executor(pool, func, *args)
