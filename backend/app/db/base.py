import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Dialect, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def get_utc_now() -> datetime:
    return datetime.now(UTC)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """
    SQLAlchemy TypeDecorator that guarantees timezone-aware UTC datetime objects.
    Ensures that values stored and retrieved always have tzinfo=datetime.timezone.utc.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect: Dialect) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return value

    def process_result_value(self, value: datetime | None, _dialect: Dialect) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return value


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=get_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID-based string primary key."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
