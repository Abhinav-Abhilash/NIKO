from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UTCDateTime, UUIDMixin


class Memory(Base, UUIDMixin, TimestampMixin):
    """
    Long-term persistent user memory record.
    Synchronized with SQLite FTS5 virtual table (memories_fts) for BM25 full-text search.
    """

    __tablename__ = "memories"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )  # Synonyms, aliases, related terms extracted by light model
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(20), default="user_stated", nullable=False
    )  # user_stated | suggested | untrusted
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    user: Mapped["User"] = relationship("User", backref="memories")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_memories_user_category", "user_id", "category"),
        Index("ix_memories_user_pinned", "user_id", "pinned"),
    )


def init_memory_fts5_schema(sync_conn: Any) -> None:
    """Creates the SQLite memories_fts virtual table and sync triggers."""
    from sqlalchemy import text

    sync_conn.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5("
            "memory_id UNINDEXED, content, keywords, key, category, tokenize='porter unicode61');"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN "
            "INSERT INTO memories_fts(memory_id, content, keywords, key, category) "
            "VALUES (new.id, new.content, coalesce(new.keywords, ''), coalesce(new.key, ''), coalesce(new.category, '')); END;"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN "
            "DELETE FROM memories_fts WHERE memory_id = old.id; END;"
        )
    )
    sync_conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN "
            "DELETE FROM memories_fts WHERE memory_id = old.id; "
            "INSERT INTO memories_fts(memory_id, content, keywords, key, category) "
            "VALUES (new.id, new.content, coalesce(new.keywords, ''), coalesce(new.key, ''), coalesce(new.category, '')); END;"
        )
    )

