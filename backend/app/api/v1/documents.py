from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_user
from backend.app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Local Document Q&A"])


class IngestDocumentRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to the local document to ingest.")
    title: str | None = Field(default=None, description="Optional custom document title.")


@router.get("")
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all indexed local documents for the current user."""
    service = DocumentService(db)
    docs = await service.list_documents(user_id=user.id)
    return {
        "documents": [
            {
                "id": d.id,
                "title": d.title,
                "file_path": d.file_path,
                "file_type": d.file_type,
                "file_size_bytes": d.file_size_bytes,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "total": len(docs),
    }


@router.post("/ingest")
async def ingest_document(
    payload: IngestDocumentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ingest, extract, chunk, and index a local file into SQLite FTS5."""
    service = DocumentService(db)
    try:
        doc = await service.ingest_file(
            user_id=user.id,
            file_path_str=payload.file_path,
            title=payload.title,
        )
        return {
            "success": True,
            "document": {
                "id": doc.id,
                "title": doc.title,
                "file_path": doc.file_path,
                "chunk_count": doc.chunk_count,
                "file_type": doc.file_type,
            },
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/search")
async def search_documents(
    query: str = Query(..., min_length=1, description="Keywords or text query to search"),
    top_k: int = Query(default=5, ge=1, le=20, description="Max results to return"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search document chunks using SQLite FTS5 BM25 ranking."""
    service = DocumentService(db)
    results = await service.search(user_id=user.id, query=query, top_k=top_k)
    return {"query": query, "results_count": len(results), "chunks": results}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete an indexed document and its chunks."""
    service = DocumentService(db)
    await service.delete_document(user_id=user.id, document_id=document_id)
    return {"success": True, "message": f"Document '{document_id}' removed."}
