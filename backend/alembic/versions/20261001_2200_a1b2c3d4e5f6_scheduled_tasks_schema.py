"""scheduled_tasks_schema

Revision ID: a1b2c3d4e5f6
Revises: e4b1091d9ce3
Create Date: 2026-10-01 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "e4b1091d9ce3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_type", sa.String(length=20), server_default="interval", nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=30), server_default="skill", nullable=False),
        sa.Column("action_name", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_json", sa.Text(), nullable=True),
        sa.Column("total_runs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_tasks_user_id", "scheduled_tasks", ["user_id"])
    op.create_index("ix_scheduled_tasks_status", "scheduled_tasks", ["status"])
    op.create_index("ix_scheduled_tasks_next_run_at", "scheduled_tasks", ["next_run_at"])
    op.create_index("ix_scheduled_tasks_user_status", "scheduled_tasks", ["user_id", "status"])
    op.create_index("ix_scheduled_tasks_due", "scheduled_tasks", ["status", "next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_tasks_due", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_user_status", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_next_run_at", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_status", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_user_id", table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")
