from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError
from backend.app.core.logging import request_id_ctx
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_owner
from backend.app.services.skill_service import SkillService
from backend.app.skills.base import AutonomyPolicy, SkillContext

router = APIRouter(prefix="/skills", tags=["Skills & Capabilities"])


class SkillResponse(BaseModel):
    name: str
    description: str
    default_tier: str
    autonomy_policy: str
    enabled: bool
    timeout_seconds: int
    parameters_schema: dict[str, Any]


class SkillUpdatePayload(BaseModel):
    autonomy_policy: AutonomyPolicy | None = Field(
        default=None,
        description="Autonomy mode: 'ask' (always prompt), 'auto' (run freely), 'auto+log' (run with audit toast)",
    )
    enabled: bool | None = Field(default=None, description="Whether the skill is active")
    timeout_seconds: int | None = Field(default=None, ge=1, le=300, description="Max execution timeout in seconds")


class SkillExecutePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, Any] = Field(default_factory=dict, description="Skill execution input parameters")
    elevated_mode: bool = Field(default=False, description="Whether elevated execution mode is enabled")


class SkillExecuteResponse(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


@router.get("", response_model=list[SkillResponse])
async def list_skills(
    _current_user: Annotated[User, Depends(get_current_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all available skills enriched with their database autonomy settings."""
    service = SkillService(db)
    return await service.list_skills()


@router.patch("/{name}", response_model=SkillResponse)
async def update_skill_config(
    name: Annotated[str, Path(description="Skill name identifier")],
    payload: SkillUpdatePayload,
    current_user: Annotated[User, Depends(get_current_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Update owner autonomy policy, timeout, or enabled flag for a skill.
    Stored persistently in the database, allowing full user customization without hardcoded locks.
    """
    service = SkillService(db)
    config = await service.update_skill_autonomy(
        name=name,
        autonomy_policy=payload.autonomy_policy,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
    )

    req_id = request_id_ctx.get()
    await service.audit_service.record_command(
        request_id=req_id,
        skill_name=name,
        permission_tier="CONFIRM",
        provenance="direct",
        arguments={
            "action": "update_skill_config",
            "autonomy_policy": payload.autonomy_policy,
            "enabled": payload.enabled,
            "timeout_seconds": payload.timeout_seconds,
        },
        status="success",
        user_id=str(current_user.id),
    )
    await db.commit()

    manifest = service.registry.get(name).manifest
    return {
        "name": config.name,
        "description": config.description,
        "default_tier": config.default_tier,
        "autonomy_policy": config.autonomy_policy,
        "enabled": config.enabled,
        "timeout_seconds": config.timeout_seconds,
        "parameters_schema": manifest.parameters_schema,
    }


@router.post("/{name}/execute", response_model=SkillExecuteResponse)
async def execute_skill(
    name: Annotated[str, Path(description="Skill name identifier")],
    payload: SkillExecutePayload,
    current_user: Annotated[User, Depends(get_current_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SkillExecuteResponse:
    """
    Execute a skill with guard validation, provenance tracking, and audit logging.
    """
    service = SkillService(db)
    if not service.registry.has(name):
        raise NotFoundError(f"Skill '{name}' is not registered.")

    req_id = request_id_ctx.get()
    # Provenance is derived strictly server-side: direct API calls by the authenticated owner are 'direct'
    context = SkillContext(
        request_id=req_id,
        user_id=str(current_user.id),
        provenance="direct",
    )

    result = await service.execute_skill(
        name=name,
        arguments=payload.arguments,
        context=context,
        elevated_mode=payload.elevated_mode,
    )
    await db.commit()

    return SkillExecuteResponse(
        success=result.success,
        data=result.data,
        error=result.error,
        execution_time_ms=result.execution_time_ms,
    )


class UndoCancelResponse(BaseModel):
    undo_id: str
    cancelled: bool


@router.post("/undo/{undo_id}/cancel", response_model=UndoCancelResponse)
async def cancel_pending_undo(
    undo_id: Annotated[str, Path(description="The unique undo operation identifier")],
    _current_user: Annotated[User, Depends(get_current_owner)],
) -> UndoCancelResponse:
    """Cancel a skill execution during its active 5-second undo delay window."""
    cancelled = SkillService.cancel_undo(undo_id)
    return UndoCancelResponse(undo_id=undo_id, cancelled=cancelled)
