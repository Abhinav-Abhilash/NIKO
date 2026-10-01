import re
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError
from backend.app.core.logging import get_logger
from backend.app.db.models.document import Document, DocumentChunk, init_document_fts5_schema

logger = get_logger("document_service")


def extract_text_from_file(file_path: Path) -> list[tuple[int | None, str]]:
    """
    Extract text from file.
    Returns list of (page_number, text_content) tuples.
    """
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        try:
            # Try pypdf if available
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages = []
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append((idx + 1, page_text))
            if pages:
                return pages
        except Exception:
            pass

        # Fallback raw byte text extraction for PDF if pypdf unavailable
        raw_bytes = file_path.read_bytes()
        # Find ASCII/UTF-8 streams
        strings = re.findall(rb"[A-Za-z0-9\s.,!?:;'\-_\(\)\[\]\/]{4,}", raw_bytes)
        fallback_text = "\n".join(s.decode("utf-8", errors="ignore") for s in strings)
        return [(1, fallback_text or "PDF binary content")]

    else:
        # Plain text, markdown, code, json, etc.
        text_content = file_path.read_text(encoding="utf-8", errors="ignore")
        return [(None, text_content)]


def chunk_text(
    text_content: str,
    chunk_size: int = 1500,
    overlap: int = 200,
) -> list[str]:
    """Split text into overlapping sliding-window character chunks."""
    if not text_content or not text_content.strip():
        return []

    cleaned = text_content.strip()
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    while start < len(cleaned):
        end = start + chunk_size
        chunk = cleaned[start:end]
        chunks.append(chunk.strip())
        start += (chunk_size - overlap)

    return [c for c in chunks if c]


class DocumentService:
    """
    Local Document Q&A / RAG service.
    Handles text extraction, sliding-window chunking, SQLite FTS5 BM25 search,
    and chat context injection.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure_fts5_schema(self) -> None:
        """Initialize document FTS5 virtual table and triggers if not already present."""
        def _sync_init(connection: Any) -> None:
            init_document_fts5_schema(connection)

        await self.db.run_sync(_sync_init)

    async def ingest_file(
        self,
        user_id: str,
        file_path_str: str,
        title: str | None = None,
    ) -> Document:
        """
        Ingest a local document, extract text, chunk, and index into SQLite FTS5.
        """
        await self.ensure_fts5_schema()
        p = Path(file_path_str).resolve()
        if not p.exists() or not p.is_file():
            raise NotFoundError(f"File not found: '{file_path_str}'")

        doc_title = title or p.name
        file_type = p.suffix.lstrip(".").lower() or "text"
        file_size = p.stat().st_size

        # Remove existing document with same path if re-ingesting
        existing_res = await self.db.execute(
            select(Document).where(Document.user_id == user_id, Document.file_path == str(p))
        )
        existing_doc = existing_res.scalar_one_or_none()
        if existing_doc:
            await self.db.delete(existing_doc)
            await self.db.flush()

        # Extract and chunk
        pages = extract_text_from_file(p)
        doc = Document(
            user_id=user_id,
            title=doc_title,
            file_path=str(p),
            file_type=file_type,
            file_size_bytes=file_size,
            chunk_count=0,
        )
        self.db.add(doc)
        await self.db.flush()

        chunk_idx = 0
        for page_num, page_content in pages:
            chunks = chunk_text(page_content)
            for c in chunks:
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk_idx,
                    content=c,
                    page_number=page_num,
                    token_count=max(1, len(c) // 4),
                )
                self.db.add(chunk_obj)
                chunk_idx += 1

        doc.chunk_count = chunk_idx
        await self.db.commit()
        await self.db.refresh(doc)
        logger.info("Ingested document", doc_id=doc.id, title=doc.title, chunks=chunk_idx)
        return doc

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search document chunks using SQLite FTS5 BM25 ranking.
        """
        await self.ensure_fts5_schema()
        cleaned_query = re.sub(r'[^\w\s]', " ", query).strip()
        if not cleaned_query:
            return []

        # Tokenize words for FTS5 match query
        terms = cleaned_query.split()
        fts_query = " OR ".join(f'"{t}"*' for t in terms)

        sql = text(
            """
            SELECT
                dc.id AS chunk_id,
                dc.document_id AS document_id,
                dc.chunk_index AS chunk_index,
                dc.page_number AS page_number,
                dc.content AS content,
                d.title AS document_title,
                d.file_path AS file_path,
                bm25(document_chunks_fts) AS rank_score
            FROM document_chunks_fts
            JOIN document_chunks dc ON dc.id = document_chunks_fts.chunk_id
            JOIN documents d ON d.id = dc.document_id
            WHERE document_chunks_fts MATCH :query
              AND d.user_id = :user_id
            ORDER BY rank_score ASC
            LIMIT :limit
            """
        )

        res = await self.db.execute(sql, {"query": fts_query, "user_id": user_id, "limit": top_k})
        rows = res.mappings().all()

        results = []
        for r in rows:
            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "document_title": r["document_title"],
                "file_path": r["file_path"],
                "chunk_index": r["chunk_index"],
                "page_number": r["page_number"],
                "content": r["content"],
                "rank_score": round(float(r["rank_score"]), 4),
            })
        return results

    async def list_documents(self, user_id: str) -> list[Document]:
        """List all indexed documents for user."""
        res = await self.db.execute(
            select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
        )
        return list(res.scalars().all())

    async def delete_document(self, user_id: str, document_id: str) -> bool:
        """Delete document and all associated chunks."""
        res = await self.db.execute(
            select(Document).where(Document.user_id == user_id, Document.id == document_id)
        )
        doc = res.scalar_one_or_none()
        if not doc:
            raise NotFoundError(f"Document '{document_id}' not found.")

        await self.db.delete(doc)
        await self.db.commit()
        return True
