from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.db.models import User
from backend.app.dependencies import get_current_owner
from backend.app.services.backup_service import BackupService
from backend.app.services.janitor_service import JanitorService

router = APIRouter(prefix="/storage", tags=["Storage Manager & Automated Maintenance"])


@router.get("/status")
async def get_storage_status(
    _current_owner: User = Depends(get_current_owner),
) -> dict[str, Any]:
    """Retrieve disk utilization metrics across database, backups, screenshots, and logs."""
    janitor = JanitorService()
    return janitor.get_storage_status()


@router.post("/backup")
async def trigger_database_backup(
    _current_owner: User = Depends(get_current_owner),
) -> dict[str, Any]:
    """Trigger an immediate safe online SQLite WAL backup."""
    backup_service = BackupService()
    try:
        return backup_service.create_backup()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {e}",
        ) from e


@router.get("/backups")
async def list_database_backups(
    _current_owner: User = Depends(get_current_owner),
) -> dict[str, Any]:
    """List available SQLite snapshots ordered by creation time descending."""
    backup_service = BackupService()
    backups = backup_service.list_backups()
    return {"backups": backups, "count": len(backups)}


@router.delete("/backups/{filename}")
async def delete_database_backup(
    filename: str,
    _current_owner: User = Depends(get_current_owner),
) -> dict[str, Any]:
    """Delete a specific backup file."""
    backup_service = BackupService()
    try:
        deleted = backup_service.delete_backup(filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup '{filename}' not found.")

    return {"status": "deleted", "filename": filename}


@router.post("/maintenance")
async def trigger_maintenance_cycle(
    _current_owner: User = Depends(get_current_owner),
) -> dict[str, Any]:
    """Trigger an immediate maintenance sweep (7-day screenshot purge, 50MB log cap, backup pruning)."""
    janitor = JanitorService()
    return janitor.run_maintenance_cycle()
