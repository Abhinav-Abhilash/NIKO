import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.events import get_event_bus
from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.db.models import Reminder, User
from backend.app.db.session import get_session_maker

logger = get_logger("reminder_service")


class ReminderService:
    """
    Manages persistent scheduled reminders in SQLite.
    Runs a non-blocking background polling worker that fires notifications
    over the async event bus and WebSocket channels.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self.db_session = db_session
        self.session_factory = session_factory or get_session_maker()
        self.poll_interval = poll_interval_seconds
        self._worker_task: asyncio.Task[None] | None = None
        self._running = False

    async def create_reminder(
        self,
        title: str,
        trigger_at: datetime,
        description: str | None = None,
        user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> Reminder:
        """Create a new scheduled reminder."""
        if not title.strip():
            raise ValidationFailedError("Reminder title cannot be empty.")

        if trigger_at.tzinfo is None:
            trigger_at = trigger_at.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        if trigger_at <= now:
            raise ValidationFailedError(
                f"Reminder trigger time ({trigger_at.isoformat()}) must be in the future (current: {now.isoformat()})."
            )

        target_session = session or self.db_session
        should_commit = False

        if not target_session:
            target_session = self.session_factory()
            should_commit = True

        try:
            # If user_id is not specified, resolve first owner user
            if not user_id:
                user_res = await target_session.execute(select(User).limit(1))
                first_user = user_res.scalar_one_or_none()
                if first_user:
                    user_id = first_user.id
                else:
                    # Create default local owner to satisfy foreign key constraint
                    default_user = User(
                        username="operator",
                        password_hash="system_managed",
                        role="owner",
                    )
                    target_session.add(default_user)
                    await target_session.flush()
                    user_id = default_user.id

            reminder = Reminder(
                user_id=user_id,
                title=title.strip(),
                description=description.strip() if description else None,
                trigger_at=trigger_at,
                status="scheduled",
            )
            target_session.add(reminder)
            if should_commit:
                await target_session.commit()
                await target_session.refresh(reminder)
            else:
                await target_session.flush()

            logger.info(
                "Created reminder",
                reminder_id=reminder.id,
                title=reminder.title,
                trigger_at=reminder.trigger_at.isoformat(),
            )
            return reminder

        finally:
            if should_commit and target_session:
                await target_session.close()

    async def list_reminders(
        self,
        user_id: str | None = None,
        status: str = "scheduled",
        session: AsyncSession | None = None,
    ) -> list[Reminder]:
        """List reminders filtered by status."""
        target_session = session or self.db_session
        should_close = False

        if not target_session:
            target_session = self.session_factory()
            should_close = True

        try:
            query = select(Reminder)
            if user_id:
                query = query.where(Reminder.user_id == user_id)
            if status != "all":
                query = query.where(Reminder.status == status)

            query = query.order_by(Reminder.trigger_at.asc())
            res = await target_session.execute(query)
            return list(res.scalars().all())

        finally:
            if should_close and target_session:
                await target_session.close()

    async def cancel_reminder(
        self,
        reminder_id: str,
        user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> Reminder:
        """Cancel an existing reminder."""
        target_session = session or self.db_session
        should_commit = False

        if not target_session:
            target_session = self.session_factory()
            should_commit = True

        try:
            query = select(Reminder).where(Reminder.id == reminder_id)
            if user_id:
                query = query.where(Reminder.user_id == user_id)

            res = await target_session.execute(query)
            reminder = res.scalar_one_or_none()
            if not reminder:
                raise NotFoundError(f"Reminder '{reminder_id}' not found.")

            reminder.status = "cancelled"
            if should_commit:
                await target_session.commit()
                await target_session.refresh(reminder)
            else:
                await target_session.flush()

            logger.info("Cancelled reminder", reminder_id=reminder_id)
            return reminder

        finally:
            if should_commit and target_session:
                await target_session.close()

    async def get_reminder(
        self,
        reminder_id: str,
        session: AsyncSession | None = None,
    ) -> Reminder:
        """Get reminder by ID."""
        target_session = session or self.db_session
        should_close = False

        if not target_session:
            target_session = self.session_factory()
            should_close = True

        try:
            query = select(Reminder).where(Reminder.id == reminder_id)
            res = await target_session.execute(query)
            reminder = res.scalar_one_or_none()
            if not reminder:
                raise NotFoundError(f"Reminder '{reminder_id}' not found.")
            return reminder

        finally:
            if should_close and target_session:
                await target_session.close()

    # ---------------------------------------------------------
    # Background Scheduling & Firing Loop
    # ---------------------------------------------------------

    async def check_and_fire_pending_reminders(self) -> int:
        """Check for due reminders, mark them as fired, and broadcast events."""
        now = datetime.now(UTC)
        fired_count = 0

        async with self.session_factory() as session:
            try:
                query = (
                    select(Reminder)
                    .where(Reminder.status == "scheduled")
                    .where(Reminder.trigger_at <= now)
                )
                res = await session.execute(query)
                due_reminders = list(res.scalars().all())

                for reminder in due_reminders:
                    reminder.status = "fired"
                    fired_count += 1

                    # Dispatch event via EventBus
                    event_bus = get_event_bus()
                    await event_bus.publish(
                        "notifications",
                        "reminder_fired",
                        {
                            "reminder_id": reminder.id,
                            "title": reminder.title,
                            "description": reminder.description,
                            "trigger_at": reminder.trigger_at.isoformat(),
                            "fired_at": now.isoformat(),
                        },
                    )

                    logger.info(
                        "Fired reminder",
                        reminder_id=reminder.id,
                        title=reminder.title,
                    )

                if fired_count > 0:
                    await session.commit()

            except Exception as exc:
                await session.rollback()
                logger.error("Error during reminder check/fire loop", error=str(exc))

        return fired_count

    async def _worker_loop(self) -> None:
        """Continuous background loop checking for due reminders."""
        while self._running:
            try:
                await self.check_and_fire_pending_reminders()
            except Exception as exc:
                logger.error("Unhandled error in reminder worker", error=str(exc))

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    async def start_background_worker(self) -> None:
        """Start the async background reminder loop."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Started background reminder worker loop", interval=self.poll_interval)

    async def stop_background_worker(self) -> None:
        """Stop the async background reminder loop."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
            logger.info("Stopped background reminder worker")


# Global singleton instance
_global_reminder_service: ReminderService | None = None


def get_reminder_service() -> ReminderService:
    global _global_reminder_service
    if _global_reminder_service is None:
        _global_reminder_service = ReminderService()
    return _global_reminder_service
