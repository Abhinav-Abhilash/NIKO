from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_user
from backend.app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


class MemoryResponse(BaseModel):
    id: str
    user_id: str
    key: str | None
    content: str
    keywords: str | None
    category: str
    source: str
    pinned: bool
    enabled: bool
    created_at: str
    updated_at: str
    last_used_at: str | None


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    key: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    pinned: bool | None = None
    enabled: bool | None = None


class MemoryConfigResponse(BaseModel):
    mode: str
    enabled: bool


class MemoryConfigUpdateRequest(BaseModel):
    mode: str | None = Field(default=None, pattern="^(manual|suggest|auto)$")
    enabled: bool | None = None


def _format_memory(m: Any) -> dict[str, Any]:
    return {
        "id": m.id,
        "user_id": m.user_id,
        "key": m.key,
        "content": m.content,
        "keywords": m.keywords,
        "category": m.category,
        "source": m.source,
        "pinned": m.pinned,
        "enabled": m.enabled,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
        "last_used_at": m.last_used_at.isoformat() if m.last_used_at else None,
    }


@router.get("/config", response_model=MemoryConfigResponse)
async def get_memory_config(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve current long-term memory governance mode and enabled status."""
    service = MemoryService(db)
    mode = await service.get_memory_mode()
    enabled = await service.is_memory_enabled()
    return {"mode": mode, "enabled": enabled}


@router.put("/config", response_model=MemoryConfigResponse)
async def update_memory_config(
    req: MemoryConfigUpdateRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update memory governance mode (manual | suggest | auto) or toggle memory on/off."""
    service = MemoryService(db)
    current_mode = await service.get_memory_mode()
    mode = req.mode or current_mode
    try:
        await service.set_memory_mode(mode=mode, enabled=req.enabled)
        await db.commit()
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "mode": await service.get_memory_mode(),
        "enabled": await service.is_memory_enabled(),
    }


@router.get("/export", response_model=list[dict[str, Any]])
async def export_memories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Export all stored memories for the authenticated operator."""
    service = MemoryService(db)
    return await service.export_memories(user_id=user.id)


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    query: str | None = Query(default=None, description="Optional search query using FTS5 BM25"),
    category: str | None = Query(default=None, description="Filter by category"),
    pinned_only: bool = Query(default=False, description="Filter only pinned memories"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List or search memories for the authenticated operator."""
    service = MemoryService(db)
    if query:
        memories = await service.recall(
            user_id=user.id,
            query=query,
            limit=limit,
            category=category,
        )
    else:
        memories = await service.list_memories(
            user_id=user.id,
            category=category,
            pinned_only=pinned_only,
            limit=limit,
            offset=offset,
        )
    return [_format_memory(m) for m in memories]


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve a single memory by ID."""
    service = MemoryService(db)
    memory = await service.get_memory(memory_id=memory_id, user_id=user.id)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    return _format_memory(memory)


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    req: MemoryUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Edit memory content or metadata (key, category, pinned, enabled)."""
    service = MemoryService(db)
    try:
        updated = await service.update_memory(
            memory_id=memory_id,
            user_id=user.id,
            content=req.content,
            key=req.key,
            category=req.category,
            pinned=req.pinned,
            enabled=req.enabled,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
        await db.commit()
        return _format_memory(updated)
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{memory_id}", status_code=status.HTTP_200_OK)
async def delete_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a memory by ID."""
    service = MemoryService(db)
    deleted = await service.forget(user_id=user.id, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    await db.commit()
    return {"deleted": True, "memory_id": memory_id}
