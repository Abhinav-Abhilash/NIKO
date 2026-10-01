import asyncio
import json
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.events import get_event_bus
from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.db.models import SkillConfig, ToolCall
from backend.app.services.approval_service import ApprovalService
from backend.app.services.audit_service import AuditService
from backend.app.skills.base import AutonomyPolicy, SkillContext, SkillExecutor, SkillResult
from backend.app.skills.builtin.clipboard_skill import ClipboardSkill
from backend.app.skills.builtin.datetime_skill import DateTimeSkill

from backend.app.skills.builtin.memory_skills import (
    ForgetSkill,
    ListMemoriesSkill,
    RecallSkill,
    RememberSkill,
)
from backend.app.skills.builtin.open_app_skill import OpenAppSkill
from backend.app.skills.builtin.reminders_skill import RemindersSkill
from backend.app.skills.builtin.schedule_task_skill import ScheduleTaskSkill
from backend.app.skills.builtin.screenshot_skill import ScreenshotSkill
from backend.app.skills.builtin.system_stats_skill import SystemStatsSkill
from backend.app.skills.builtin.volume_brightness_skill import VolumeBrightnessSkill
from backend.app.skills.builtin.web_search_skill import WebSearchSkill
from backend.app.skills.builtin.youtube_play_skill import YouTubePlaySkill
from backend.app.skills.executor import LocalExecutor
from backend.app.skills.guard import SkillGuard
from backend.app.skills.registry import SkillRegistry, get_skill_registry

logger = get_logger("skill_service")


class SkillService:
    """
    High-level skill management service.
    Coordinates skill lookup, database configuration sync, provenance guarding,
    approval requests, execution, and audit logging.
    """

    _active_undo_cancels: ClassVar[dict[str, asyncio.Event]] = {}

    @classmethod
    def cancel_undo(cls, undo_id: str) -> bool:
        """Trigger cancellation of a pending undo window. Returns True if cancelled."""
        event = cls._active_undo_cancels.get(undo_id)
        if event:
            event.set()
            return True
        return False

    def __init__(
        self,
        db: AsyncSession,
        registry: SkillRegistry | None = None,
        executor: SkillExecutor | None = None,
        undo_window_seconds: float = 5.0,
    ) -> None:
        self.db = db
        self.registry = registry or get_skill_registry()
        self.executor = executor or LocalExecutor()
        self.audit_service = AuditService(db)
        self.approval_service = ApprovalService(db)
        self.undo_window_seconds = undo_window_seconds

    async def initialize_builtin_skills(self) -> None:
        """Register built-in skills and sync default configurations into SQLite."""
        builtin_skill_instances = [
            ClipboardSkill(),
            DateTimeSkill(),
            SystemStatsSkill(),

            OpenAppSkill(),
            WebSearchSkill(),
            YouTubePlaySkill(),
            ScreenshotSkill(),
            VolumeBrightnessSkill(),
            RemindersSkill(),
            ScheduleTaskSkill(),
            RememberSkill(),
            RecallSkill(),
            ForgetSkill(),
            ListMemoriesSkill(),
        ]
        for skill in builtin_skill_instances:
            if not self.registry.has(skill.manifest.name):
                self.registry.register(skill)

        for manifest in self.registry.list_manifests():
            query = select(SkillConfig).where(SkillConfig.name == manifest.name)
            res = await self.db.execute(query)
            existing = res.scalar_one_or_none()

            if not existing:
                config = SkillConfig(
                    name=manifest.name,
                    description=manifest.description,
                    default_tier=manifest.default_tier,
                    autonomy_policy=manifest.default_autonomy,
                    enabled=True,
                    timeout_seconds=manifest.timeout_seconds,
                    config_json="{}",
                )
                self.db.add(config)
        await self.db.flush()

    async def get_skill_config(self, name: str) -> SkillConfig | None:
        """Fetch database-backed skill configuration."""
        query = select(SkillConfig).where(SkillConfig.name == name)
        res = await self.db.execute(query)
        return res.scalar_one_or_none()

    async def list_skills(self) -> list[dict[str, Any]]:
        """Return all registered skills enriched with database autonomy settings."""
        await self.initialize_builtin_skills()
        configs = {
            c.name: c
            for c in (await self.db.execute(select(SkillConfig))).scalars().all()
        }

        output = []
        for manifest in self.registry.list_manifests():
            db_cfg = configs.get(manifest.name)
            output.append(
                {
                    "name": manifest.name,
                    "description": manifest.description,
                    "default_tier": manifest.default_tier,
                    "autonomy_policy": db_cfg.autonomy_policy if db_cfg else manifest.default_autonomy,
                    "enabled": db_cfg.enabled if db_cfg else True,
                    "timeout_seconds": db_cfg.timeout_seconds if db_cfg else manifest.timeout_seconds,
                    "parameters_schema": manifest.parameters_schema,
                }
            )
        return output

    async def update_skill_autonomy(
        self,
        name: str,
        autonomy_policy: AutonomyPolicy | None = None,
        enabled: bool | None = None,
        timeout_seconds: int | None = None,
    ) -> SkillConfig:
        """Update owner-configurable autonomy policy, active status, or timeout for a skill."""
        await self.initialize_builtin_skills()
        config = await self.get_skill_config(name)
        if not config:
            raise NotFoundError(f"Skill '{name}' was not found in configuration.")

        if autonomy_policy:
            if autonomy_policy not in ("ask", "auto", "auto+log"):
                raise ValidationFailedError(
                    f"Invalid autonomy policy '{autonomy_policy}'. Must be 'ask', 'auto', or 'auto+log'."
                )
            config.autonomy_policy = autonomy_policy

        if enabled is not None:
            config.enabled = enabled

        if timeout_seconds is not None:
            if timeout_seconds < 1 or timeout_seconds > 300:
                raise ValidationFailedError("Timeout seconds must be between 1 and 300.")
            config.timeout_seconds = timeout_seconds

        await self.db.flush()
        logger.info(
            "Updated skill configuration",
            name=name,
            autonomy=config.autonomy_policy,
            enabled=config.enabled,
        )
        return config

    async def execute_skill(
        self,
        name: str,
        arguments: dict[str, Any],
        context: SkillContext,
        elevated_mode: bool = False,
    ) -> SkillResult:
        """
        Evaluate guard rules, handle approvals, execute skill, and record audit trail.
        """
        if not self.registry.has(name):
            await self.initialize_builtin_skills()

        if not self.registry.has(name):
            return SkillResult(
                success=False,
                error=f"Skill '{name}' is not registered.",
            )

        skill = self.registry.get(name)
        db_cfg = await self.get_skill_config(name)

        if db_cfg and not db_cfg.enabled:
            return SkillResult(
                success=False,
                error=f"Skill '{name}' is currently disabled in settings.",
            )

        # 1. Evaluate guard and provenance rule
        decision = SkillGuard.evaluate(
            manifest=skill.manifest,
            context=context,
            stored_config=db_cfg,
            elevated_mode=elevated_mode,
        )

        # Pre-validate and canonicalize arguments for open_app before staging approval or execution
        if name == "open_app":
            from backend.app.core.security import canonicalize_open_app_arguments
            arguments = canonicalize_open_app_arguments(arguments)

        # 2. Check if human approval is required
        if decision.requires_approval:
            # Need to stage approval request
            logger.info("Human confirmation required for skill execution", skill=name, reason=decision.reason)
            tool_call = ToolCall(
                skill_name=name,
                arguments_json=json.dumps(arguments),
                status="awaiting_approval",
            )
            self.db.add(tool_call)
            await self.db.flush()

            approval = await self.approval_service.create_approval(
                tool_call_id=tool_call.id,
                arguments=arguments,
                skill_name=name,
                expires_in_seconds=30,
            )
            # Record audit as awaiting approval / blocked until confirmed
            await self.audit_service.record_command(
                request_id=context.request_id,
                skill_name=name,
                permission_tier=decision.effective_tier,
                provenance=context.provenance,
                arguments=arguments,
                status="pending_approval",
                user_id=context.user_id,
                approval_id=approval.id,
            )
            return SkillResult(
                success=False,
                error="CONFIRMATION_REQUIRED",
                data={
                    "approval_id": approval.id,
                    "args_hash": approval.args_hash,
                    "reason": decision.reason,
                    "expires_at": approval.expires_at.isoformat(),
                    "skill_name": name,
                    "arguments": arguments,
                },
            )

        if not decision.execute_immediately:
            await self.audit_service.record_command(
                request_id=context.request_id,
                skill_name=name,
                permission_tier=decision.effective_tier,
                provenance=context.provenance,
                arguments=arguments,
                status="blocked",
                user_id=context.user_id,
            )
            return SkillResult(success=False, error=decision.reason)

        # 3. If undo window is required (e.g. actions proposed downstream of untrusted content),
        # delay execution until the window closes without a cancel.
        if decision.requires_toast_undo:
            undo_id = f"undo_{context.request_id}"
            cancel_event = asyncio.Event()
            self._active_undo_cancels[undo_id] = cancel_event

            event_bus = get_event_bus()
            await event_bus.publish(
                topic="sys",
                event_type="toast_undo",
                payload={
                    "undo_id": undo_id,
                    "skill_name": name,
                    "window_seconds": self.undo_window_seconds,
                    "reason": decision.reason,
                },
            )

            logger.info(
                "Skill execution delayed for undo window",
                skill=name,
                undo_id=undo_id,
                window_seconds=self.undo_window_seconds,
            )
            try:
                try:
                    await asyncio.wait_for(cancel_event.wait(), timeout=self.undo_window_seconds)
                    was_cancelled = True
                except TimeoutError:
                    was_cancelled = False
            finally:
                self._active_undo_cancels.pop(undo_id, None)

            if was_cancelled:
                logger.info("Skill execution cancelled by user during undo window", skill=name, undo_id=undo_id)
                await self.audit_service.record_command(
                    request_id=context.request_id,
                    skill_name=name,
                    permission_tier=decision.effective_tier,
                    provenance=context.provenance,
                    arguments=arguments,
                    status="cancelled_by_user",
                    user_id=context.user_id,
                )
                return SkillResult(
                    success=False,
                    error="CANCELLED_BY_USER",
                    data={"undo_id": undo_id, "reason": "Execution cancelled during undo window."},
                )

        # 4. Execute via LocalExecutor under timeout barrier
        result = await self.executor.execute(skill, arguments, context)

        # 4. Audit execution outcome
        await self.audit_service.record_command(
            request_id=context.request_id,
            skill_name=name,
            permission_tier=decision.effective_tier,
            provenance=context.provenance,
            arguments=arguments,
            status="success" if result.success else "failed",
            user_id=context.user_id,
        )

        return result
