from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.db.models import User
from backend.app.dependencies import get_current_user
from backend.app.services.shadow_copy_service import get_shadow_copy_service

router = APIRouter(prefix="/undo", tags=["Reversible Action Shadow-Copy"])


class RevertRequest(BaseModel):
    snapshot_id: str | None = Field(default=None, description="Optional specific snapshot ID to revert. Reverts most recent if omitted.")


@router.get("/snapshots")
async def list_undo_snapshots(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """List all available file shadow snapshots in the undo staging area."""
    service = get_shadow_copy_service()
    snapshots = service.list_snapshots()
    return {"snapshots": snapshots, "total": len(snapshots)}


@router.post("/revert")
async def revert_snapshot(
    payload: RevertRequest,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Revert a shadow copy snapshot and restore original file states."""
    service = get_shadow_copy_service()
    try:
        res = service.restore_snapshot(snapshot_id=payload.snapshot_id)
        return res
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
