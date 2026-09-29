from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_owner
from backend.app.services.metrics_service import get_metrics_service

router = APIRouter(prefix="/metrics", tags=["System Telemetry & Live Metrics"])


class CurrentMetricsResponse(BaseModel):
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    battery_percent: float | None = None
    timestamp: str


class HistoricalMetricPoint(BaseModel):
    id: str
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    battery_percent: float | None = None
    timestamp: datetime


class TabVisibilityPayload(BaseModel):
    hidden: bool = Field(
        ...,
        description="Whether the client browser tab is hidden (drops polling to 15s) or visible (restores 2s cadence)",
    )


class VisibilityResponse(BaseModel):
    hidden: bool
    interval_seconds: float


@router.get("/current", response_model=CurrentMetricsResponse)
async def get_current_metrics(
    _current_user: Annotated[User, Depends(get_current_owner)],
) -> dict[str, Any]:
    """Get an immediate live snapshot of host CPU, RAM, disk, and battery."""
    service = get_metrics_service()
    return service.sample_current_metrics()


@router.get("/history", response_model=list[HistoricalMetricPoint])
async def get_metrics_history(
    _current_user: Annotated[User, Depends(get_current_owner)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1440, description="Max historical records to retrieve")] = 60,
) -> list[HistoricalMetricPoint]:
    """Retrieve 1-minute historical telemetry aggregates."""
    service = get_metrics_service()
    records = await service.get_recent_history(db=db, limit=limit)
    return [
        HistoricalMetricPoint(
            id=str(r.id),
            cpu_percent=r.cpu_percent,
            ram_percent=r.ram_percent,
            disk_percent=r.disk_percent,
            battery_percent=r.battery_percent,
            timestamp=r.timestamp,
        )
        for r in records
    ]


@router.post("/visibility", response_model=VisibilityResponse)
async def update_tab_visibility(
    payload: TabVisibilityPayload,
    _current_user: Annotated[User, Depends(get_current_owner)],
) -> VisibilityResponse:
    """
    Adjust telemetry streaming cadence dynamically based on client tab visibility.
    Active tab streams every 2 seconds; backgrounded tab throttles to 15 seconds.
    """
    service = get_metrics_service()
    service.set_tab_hidden(payload.hidden)
    return VisibilityResponse(
        hidden=service.is_tab_hidden,
        interval_seconds=service.current_interval,
    )
