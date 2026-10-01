import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_user
from backend.app.services.task_scheduler_service import TaskSchedulerService

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Task name")
    description: str | None = Field(default=None, max_length=1000, description="Optional description")
    schedule_type: str = Field(default="interval", description="interval, cron, or once")
    interval_seconds: int | None = Field(default=None, ge=1, description="Interval in seconds")
    cron_expression: str | None = Field(default=None, max_length=100, description="Cron expression")
    action_type: str = Field(default="skill", description="skill, chat_prompt, or notification")
    action_name: str = Field(..., min_length=1, max_length=100, description="Skill or action name")
    payload: dict[str, Any] = Field(default_factory=dict, description="Action arguments or payload")
    run_in_seconds: int | None = Field(default=None, ge=1, description="Relative start delay in seconds")
    next_run_at: datetime | None = Field(default=None, description="Explicit UTC next run timestamp")


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, description="active or paused")
    interval_seconds: int | None = Field(default=None, ge=1)
    cron_expression: str | None = Field(default=None, max_length=100)


class ScheduleResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None
    schedule_type: str
    cron_expression: str | None
    interval_seconds: int | None
    action_type: str
    action_name: str
    payload: dict[str, Any]
    status: str
    next_run_at: str
    last_run_at: str | None
    last_result_json: str | None
    total_runs: int
    created_at: str
    updated_at: str


def _serialize_task(task: Any) -> dict[str, Any]:
    try:
        payload = json.loads(task.payload_json) if task.payload_json else {}
    except Exception:
        payload = {}

    return {
        "id": task.id,
        "user_id": task.user_id,
        "name": task.name,
        "description": task.description,
        "schedule_type": task.schedule_type,
        "cron_expression": task.cron_expression,
        "interval_seconds": task.interval_seconds,
        "action_type": task.action_type,
        "action_name": task.action_name,
        "payload": payload,
        "status": task.status,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else "",
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "last_result_json": task.last_result_json,
        "total_runs": task.total_runs,
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "updated_at": task.updated_at.isoformat() if task.updated_at else "",
    }


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List scheduled tasks for the authenticated operator."""
    service = TaskSchedulerService(db_session=db)
    tasks = await service.list_tasks(user_id=user.id, status=status_filter)
    return [_serialize_task(t) for t in tasks]


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    req: ScheduleCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new scheduled task."""
    service = TaskSchedulerService(db_session=db)

    next_run = req.next_run_at
    if req.run_in_seconds is not None:
        next_run = datetime.now(UTC) + timedelta(seconds=req.run_in_seconds)

    task = await service.create_task(
        user_id=user.id,
        name=req.name,
        description=req.description,
        schedule_type=req.schedule_type,
        cron_expression=req.cron_expression,
        interval_seconds=req.interval_seconds,
        action_type=req.action_type,
        action_name=req.action_name,
        payload=req.payload,
        next_run_at=next_run,
    )
    return _serialize_task(task)


@router.get("/{task_id}", response_model=ScheduleResponse)
async def get_schedule(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get details for a specific scheduled task."""
    service = TaskSchedulerService(db_session=db)
    task = await service.get_task(task_id=task_id, user_id=user.id)
    return _serialize_task(task)


@router.patch("/{task_id}", response_model=ScheduleResponse)
async def update_schedule(
    task_id: str,
    req: ScheduleUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update status, interval, or metadata for a scheduled task."""
    service = TaskSchedulerService(db_session=db)
    update_data = req.model_dump(exclude_unset=True)
    status_val = update_data.pop("status", None)

    task = await service.update_task(
        task_id=task_id,
        user_id=user.id,
        status=status_val,
        **update_data,
    )
    return _serialize_task(task)


@router.delete("/{task_id}")
async def delete_schedule(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a scheduled task."""
    service = TaskSchedulerService(db_session=db)
    await service.delete_task(task_id=task_id, user_id=user.id)
    return {"success": True, "id": task_id}
