from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_user
from backend.app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Title or topic of reminder")
    description: str | None = Field(default=None, max_length=1000, description="Optional description")
    trigger_at: datetime = Field(..., description="UTC or ISO 8601 trigger datetime")


class ReminderResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None
    trigger_at: str
    status: str
    created_at: str


@router.get("", response_model=list[ReminderResponse])
async def list_reminders(
    status_filter: str = Query("scheduled", alias="status", enum=["scheduled", "fired", "cancelled", "all"]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List reminders for the authenticated operator."""
    service = ReminderService(db_session=db)
    reminders = await service.list_reminders(user_id=user.id, status=status_filter)
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "title": r.title,
            "description": r.description,
            "trigger_at": r.trigger_at.isoformat(),
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in reminders
    ]


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    req: ReminderCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new scheduled reminder."""
    service = ReminderService(db_session=db)
    trigger_at = req.trigger_at
    if trigger_at.tzinfo is None:
        trigger_at = trigger_at.replace(tzinfo=UTC)

    reminder = await service.create_reminder(
        title=req.title,
        trigger_at=trigger_at,
        description=req.description,
        user_id=user.id,
    )
    return {
        "id": reminder.id,
        "user_id": reminder.user_id,
        "title": reminder.title,
        "description": reminder.description,
        "trigger_at": reminder.trigger_at.isoformat(),
        "status": reminder.status,
        "created_at": reminder.created_at.isoformat(),
    }


@router.delete("/{reminder_id}", response_model=ReminderResponse)
async def cancel_reminder(
    reminder_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cancel an active scheduled reminder."""
    service = ReminderService(db_session=db)
    reminder = await service.cancel_reminder(reminder_id=reminder_id, user_id=user.id)
    return {
        "id": reminder.id,
        "user_id": reminder.user_id,
        "title": reminder.title,
        "description": reminder.description,
        "trigger_at": reminder.trigger_at.isoformat(),
        "status": reminder.status,
        "created_at": reminder.created_at.isoformat(),
    }
