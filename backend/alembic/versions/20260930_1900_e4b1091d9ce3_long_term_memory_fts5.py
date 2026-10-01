"""long_term_memory_fts5

Revision ID: e4b1091d9ce3
Revises: 2600a0b07ec5
Create Date: 2026-09-30 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b1091d9ce3"
down_revision: str | None = "2600a0b07ec5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create standard relational table 'memories'
    op.create_table(
        "memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="general"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="user_stated"),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_key", "memories", ["key"])
    op.create_index("ix_memories_category", "memories", ["category"])
    op.create_index("ix_memories_pinned", "memories", ["pinned"])
    op.create_index("ix_memories_enabled", "memories", ["enabled"])
    op.create_index("ix_memories_user_category", "memories", ["user_id", "category"])
    op.create_index("ix_memories_user_pinned", "memories", ["user_id", "pinned"])

    # 2. Raw-SQL: SQLite FTS5 Virtual Table with Porter Stemmer
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5("
            "memory_id UNINDEXED, content, keywords, key, category, tokenize='porter unicode61');"
        )
    )

    # 3. Raw-SQL: SQLite FTS5 Synchronization Triggers
    conn.execute(
        sa.text(
            "CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN "
            "INSERT INTO memories_fts(memory_id, content, keywords, key, category) "
            "VALUES (new.id, new.content, coalesce(new.keywords, ''), coalesce(new.key, ''), coalesce(new.category, '')); END;"
        )
    )
    conn.execute(
        sa.text(
            "CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN "
            "DELETE FROM memories_fts WHERE memory_id = old.id; END;"
        )
    )
    conn.execute(
        sa.text(
            "CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN "
            "DELETE FROM memories_fts WHERE memory_id = old.id; "
            "INSERT INTO memories_fts(memory_id, content, keywords, key, category) "
            "VALUES (new.id, new.content, coalesce(new.keywords, ''), coalesce(new.key, ''), coalesce(new.category, '')); END;"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TRIGGER IF EXISTS memories_au;"))
    conn.execute(sa.text("DROP TRIGGER IF EXISTS memories_ad;"))
    conn.execute(sa.text("DROP TRIGGER IF EXISTS memories_ai;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS memories_fts;"))

    op.drop_index("ix_memories_user_pinned", table_name="memories")
    op.drop_index("ix_memories_user_category", table_name="memories")
    op.drop_index("ix_memories_enabled", table_name="memories")
    op.drop_index("ix_memories_pinned", table_name="memories")
    op.drop_index("ix_memories_category", table_name="memories")
    op.drop_index("ix_memories_key", table_name="memories")
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_table("memories")
