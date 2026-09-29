import asyncio
import contextlib
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import psutil
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.events import EventBus, get_event_bus
from backend.app.core.logging import get_logger
from backend.app.db.models import SystemMetric

logger = get_logger("metrics_service")


class MetricsService:
    """
    Real-time system telemetry collector and historical aggregator.
    - Publishes instant `sys:metrics` events every 2s while client is active.
    - Drops to 15s interval when browser tab is hidden to conserve CPU.
    - Stops polling when zero subscribers are connected.
    - Aggregates 1-minute metrics into SQLite with 30-day retention pruning.
    """

    ACTIVE_INTERVAL: float = 2.0
    BACKGROUND_INTERVAL: float = 15.0
    DEFAULT_RETENTION_DAYS: int = 30

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.event_bus = event_bus or get_event_bus()
        self.is_tab_hidden: bool = False
        self._collector_task: asyncio.Task[None] | None = None
        self._samples_buffer: list[dict[str, float]] = []

    def set_tab_hidden(self, hidden: bool) -> None:
        """Switch sampling cadence between active (2s) and background/hidden (15s)."""
        self.is_tab_hidden = hidden
        logger.info("Metrics collector cadence adjusted", tab_hidden=hidden)

    @property
    def current_interval(self) -> float:
        return self.BACKGROUND_INTERVAL if self.is_tab_hidden else self.ACTIVE_INTERVAL

    def sample_current_metrics(self) -> dict[str, Any]:
        """Synchronously sample instant host performance indicators (non-blocking CPU)."""
        cpu_pct = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()

        root_path = "C:\\" if os.name == "nt" else "/"
        try:
            disk = psutil.disk_usage(root_path)
        except Exception:
            disk = psutil.disk_usage("/")

        battery = psutil.sensors_battery()
        battery_pct = float(battery.percent) if battery else None

        return {
            "cpu_percent": float(cpu_pct),
            "ram_percent": float(vm.percent),
            "disk_percent": float(disk.percent),
            "battery_percent": battery_pct,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def collect_and_publish_tick(self) -> dict[str, Any] | None:
        """
        Check for subscribers; if active, sample metrics, buffer for 1-minute aggregation,
        and publish `sys:metrics` event on the bus.
        """
        # Only sample and stream if clients are actively subscribed to telemetry
        if not self.event_bus.has_subscribers("sys"):
            return None

        metrics = await asyncio.to_thread(self.sample_current_metrics)

        # Buffer for 1-minute aggregate persistence
        self._samples_buffer.append(
            {
                "cpu": metrics["cpu_percent"],
                "ram": metrics["ram_percent"],
                "disk": metrics["disk_percent"],
                "battery": metrics["battery_percent"] or 0.0,
            }
        )

        await self.event_bus.publish(
            topic="sys",
            event_type="metrics",
            payload={**metrics, "interval": self.current_interval},
        )
        return metrics

    async def aggregate_and_persist(self, db: AsyncSession) -> SystemMetric | None:
        """Calculate average of buffered 1-minute samples and persist a SystemMetric row."""
        if not self._samples_buffer:
            return None

        count = len(self._samples_buffer)
        avg_cpu = sum(s["cpu"] for s in self._samples_buffer) / count
        avg_ram = sum(s["ram"] for s in self._samples_buffer) / count
        avg_disk = sum(s["disk"] for s in self._samples_buffer) / count
        has_battery = any(s["battery"] > 0 for s in self._samples_buffer)
        avg_battery = (
            sum(s["battery"] for s in self._samples_buffer) / count if has_battery else None
        )

        record = SystemMetric(
            cpu_percent=round(avg_cpu, 2),
            ram_percent=round(avg_ram, 2),
            disk_percent=round(avg_disk, 2),
            battery_percent=round(avg_battery, 2) if avg_battery is not None else None,
            timestamp=datetime.now(UTC),
        )

        db.add(record)
        await db.commit()
        self._samples_buffer.clear()
        logger.debug("Persisted 1-minute system metrics aggregate", samples_count=count)
        return record

    async def prune_stale_metrics(self, db: AsyncSession, retention_days: int = 30) -> int:
        """Enforce retention rule: purge system metric aggregates older than 30 days."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        stmt = delete(SystemMetric).where(SystemMetric.timestamp < cutoff)
        result = await db.execute(stmt)
        await db.commit()
        deleted_count = getattr(result, "rowcount", 0)
        if isinstance(deleted_count, int) and deleted_count > 0:
            logger.info("Pruned expired system metrics", count=deleted_count, retention_days=retention_days)
            return deleted_count
        return 0

    async def get_recent_history(
        self,
        db: AsyncSession,
        limit: int = 60,
    ) -> list[SystemMetric]:
        """Fetch chronological historical metrics aggregates."""
        stmt = select(SystemMetric).order_by(desc(SystemMetric.timestamp)).limit(limit)
        res = await db.execute(stmt)
        return list(reversed(res.scalars().all()))

    async def start_collector(self) -> None:
        """Start the background collector and aggregation loop."""
        if self._collector_task is not None and not self._collector_task.done():
            return

        async def _loop() -> None:
            last_aggregate_time = datetime.now(UTC)
            with contextlib.suppress(asyncio.CancelledError):
                while True:
                    await self.collect_and_publish_tick()

                    # Check 1-minute aggregation trigger
                    now = datetime.now(UTC)
                    if (now - last_aggregate_time).total_seconds() >= 60.0:
                        if self.session_factory:
                            async with self.session_factory() as db:
                                await self.aggregate_and_persist(db)
                        last_aggregate_time = now

                    await asyncio.sleep(self.current_interval)

        self._collector_task = asyncio.create_task(_loop())
        logger.info("Started background system metrics collector loop")

    async def stop_collector(self) -> None:
        """Cancel and clean up the collector loop task."""
        if self._collector_task:
            self._collector_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._collector_task
            self._collector_task = None
            logger.info("Stopped background system metrics collector loop")


# Global singleton instance
_metrics_service: MetricsService | None = None


def get_metrics_service(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> MetricsService:
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService(session_factory=session_factory)
    return _metrics_service
