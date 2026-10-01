from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin):
    """
    Ingested document metadata record for local Document Q&A / RAG.
    """

    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="text", nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User", backref="documents")  # type: ignore[name-defined] # noqa: F821


class DocumentChunk(Base, UUIDMixin, TimestampMixin):
    """
    Individual text chunk from an ingested document, indexed into SQLite FTS5.
    """

    __tablename__ = "document_chunks"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_doc_chunks_doc_idx", "document_id", "chunk_index"),
    )


def init_document_fts5_schema(sync_conn: Any) -> None:
    """Creates the SQLite document_chunks_fts virtual table and sync triggers."""
    from sqlalchemy import text

    sync_conn.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5("
            "chunk_id UNINDEXED, document_id UNINDEXED, content, tokenize='porter unicode61');"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS doc_chunks_ai AFTER INSERT ON document_chunks BEGIN "
            "INSERT INTO document_chunks_fts(chunk_id, document_id, content) "
            "VALUES (new.id, new.document_id, new.content); END;"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS doc_chunks_ad AFTER DELETE ON document_chunks BEGIN "
            "DELETE FROM document_chunks_fts WHERE chunk_id = old.id; END;"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS doc_chunks_au AFTER UPDATE ON document_chunks BEGIN "
            "DELETE FROM document_chunks_fts WHERE chunk_id = old.id; "
            "INSERT INTO document_chunks_fts(chunk_id, document_id, content) "
            "VALUES (new.id, new.document_id, new.content); END;"
        )
    )
