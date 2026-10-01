from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UTCDateTime, UUIDMixin


class ScheduledTask(Base, UUIDMixin, TimestampMixin):
    """
    Persistent scheduled task or agent cron hook.
    Supports interval seconds, cron expressions, or one-time future triggers.
    """

    __tablename__ = "scheduled_tasks"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_type: Mapped[str] = mapped_column(
        String(20), default="interval", nullable=False
    )  # interval | cron | once
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_type: Mapped[str] = mapped_column(
        String(30), default="skill", nullable=False
    )  # skill | chat_prompt | notification
    action_name: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False, index=True
    )  # active | paused | completed | failed
    next_run_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="scheduled_tasks")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        Index("ix_scheduled_tasks_user_status", "user_id", "status"),
        Index("ix_scheduled_tasks_due", "status", "next_run_at"),
    )
