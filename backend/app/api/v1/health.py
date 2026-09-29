import shutil
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.core.logging import request_id_ctx
from backend.app.db.session import get_db

router = APIRouter(tags=["Health"])

_START_TIME = time.time()


class HealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "healthy"})
    version: str = Field(..., json_schema_extra={"example": "0.1.0"})
    uptime_seconds: float
    request_id: str
    database: str = Field(..., json_schema_extra={"example": "connected"})
    storage: dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    # 1. Verify Database connectivity
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1;"))
    except Exception:
        db_status = "disconnected"

    # 2. Check Disk Free Space on host
    storage_dir = settings.get_storage_path()
    total, used, free = shutil.disk_usage(str(storage_dir))
    disk_free_gb = round(free / (1024**3), 2)
    disk_total_gb = round(total / (1024**3), 2)

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version=settings.APP_VERSION,
        uptime_seconds=round(time.time() - _START_TIME, 2),
        request_id=request_id_ctx.get(),
        database=db_status,
        storage={
            "free_gb": disk_free_gb,
            "total_gb": disk_total_gb,
            "storage_path": str(storage_dir),
        },
    )
