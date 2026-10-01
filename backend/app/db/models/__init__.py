from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UTCDateTime, UUIDMixin, get_utc_now


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New Conversation", nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    tool_calls: Mapped[list["ToolCall"]] = relationship("ToolCall", back_populates="message")

    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)


class ToolCall(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tool_calls"

    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )  # pending, awaiting_approval, running, completed, failed, rejected
    execution_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    message: Mapped["Message | None"] = relationship("Message", back_populates="tool_calls")
    approval: Mapped["Approval | None"] = relationship(
        "Approval", back_populates="tool_call", uselist=False
    )


class Approval(Base, UUIDMixin, TimestampMixin):
    """
    Core control model: single-use, auditable approval cryptographically bound
    to the exact arguments displayed to the user via args_hash.
    """

    __tablename__ = "approvals"

    tool_call_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tool_calls.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    args_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # SHA-256 hash of canonical arguments JSON
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, approved, denied, expired
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    tool_call: Mapped["ToolCall"] = relationship("ToolCall", back_populates="approval")
    command_logs: Mapped[list["CommandLog"]] = relationship("CommandLog", back_populates="approval")


class CommandLog(Base, UUIDMixin):
    __tablename__ = "command_logs"

    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approval_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_tier: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # SAFE, CONFIRM, BLOCKED
    provenance: Mapped[str] = mapped_column(
        String(30), default="direct", nullable=False
    )  # direct, external_untrusted
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # success, failed, blocked, denied
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=get_utc_now, nullable=False
    )

    approval: Mapped["Approval | None"] = relationship("Approval", back_populates="command_logs")

    __table_args__ = (Index("ix_command_logs_created_at", "created_at"),)


class SkillConfig(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    default_tier: Mapped[str] = mapped_column(String(20), default="SAFE", nullable=False)
    autonomy_policy: Mapped[str] = mapped_column(
        String(20), default="auto", nullable=False
    )  # ask, auto, auto+log
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class LLMProviderModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "llm_providers"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # gemini, groq, openrouter
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_model: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # 1 = primary, 2 = fallback, etc.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    ram_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime, default=get_utc_now, nullable=False
    )

    __table_args__ = (Index("ix_system_metrics_timestamp", "timestamp"),)


class Reminder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reminders"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", nullable=False
    )  # scheduled, fired, cancelled

    user: Mapped["User"] = relationship("User", back_populates="reminders")


class StorageReport(Base, UUIDMixin):
    __tablename__ = "storage_reports"

    db_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    screenshots_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    logs_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    free_disk_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=get_utc_now, nullable=False
    )


# Long-term memory model
from backend.app.db.models.memory import Memory  # noqa: E402

__all__ = [
    "Approval",
    "Base",
    "CommandLog",
    "Conversation",
    "LLMProviderModel",
    "Memory",
    "Message",
    "Reminder",
    "Session",
    "Setting",
    "SkillConfig",
    "StorageReport",
    "SystemMetric",
    "ToolCall",
    "User",
]
