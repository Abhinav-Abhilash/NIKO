import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.events import EventBus
from backend.app.db.models import SystemMetric
from backend.app.services.metrics_service import MetricsService


def test_metrics_service_cadence_switching() -> None:
    service = MetricsService()
    assert service.current_interval == 2.0
    assert service.is_tab_hidden is False

    service.set_tab_hidden(True)
    assert service.current_interval == 15.0
    assert service.is_tab_hidden is True

    service.set_tab_hidden(False)
    assert service.current_interval == 2.0
    assert service.is_tab_hidden is False


@pytest.mark.asyncio
async def test_metrics_service_skips_when_no_subscribers() -> None:
    bus = EventBus()
    service = MetricsService(event_bus=bus)

    # No subscribers
    result = await service.collect_and_publish_tick()
    assert result is None
    assert len(service._samples_buffer) == 0


@pytest.mark.asyncio
async def test_metrics_service_publishes_when_subscribed() -> None:
    bus = EventBus()
    service = MetricsService(event_bus=bus)

    # Subscribe to sys via AsyncGenerator
    sub_gen = bus.subscribe("sys")
    fetch_task = asyncio.create_task(anext(sub_gen))
    await asyncio.sleep(0.01)  # Allow subscription queue to register

    try:
        assert bus.has_subscribers("sys") is True

        result = await service.collect_and_publish_tick()
        assert result is not None
        assert "cpu_percent" in result
        assert "ram_percent" in result
        assert len(service._samples_buffer) == 1

        # Event should have arrived on subscriber
        event = await fetch_task
        assert event.topic == "sys"
        assert event.event_type == "metrics"
        assert event.payload["cpu_percent"] == result["cpu_percent"]
        assert event.payload["interval"] == 2.0
    finally:
        await sub_gen.aclose()


@pytest.mark.asyncio
async def test_metrics_service_aggregate_and_persist(db_session: AsyncSession) -> None:
    bus = EventBus()
    service = MetricsService(event_bus=bus)

    # Add mock samples to buffer
    service._samples_buffer = [
        {"cpu": 20.0, "ram": 50.0, "disk": 40.0, "battery": 90.0},
        {"cpu": 40.0, "ram": 60.0, "disk": 40.0, "battery": 90.0},
    ]

    record = await service.aggregate_and_persist(db_session)
    assert record is not None
    assert record.cpu_percent == 30.0  # Average of 20 and 40
    assert record.ram_percent == 55.0  # Average of 50 and 60
    assert record.disk_percent == 40.0
    assert record.battery_percent == 90.0
    assert len(service._samples_buffer) == 0

    # Query from database to verify persistence
    stored = (await db_session.execute(select(SystemMetric))).scalars().all()
    assert len(stored) >= 1


@pytest.mark.asyncio
async def test_metrics_service_prune_stale_metrics(db_session: AsyncSession) -> None:
    service = MetricsService()

    # Create one recent metric and one stale metric (35 days old)
    now = datetime.now(UTC)
    recent = SystemMetric(
        cpu_percent=15.0,
        ram_percent=45.0,
        disk_percent=30.0,
        timestamp=now - timedelta(days=5),
    )
    stale = SystemMetric(
        cpu_percent=55.0,
        ram_percent=75.0,
        disk_percent=30.0,
        timestamp=now - timedelta(days=35),
    )
    db_session.add_all([recent, stale])
    await db_session.commit()

    # Prune with 30-day retention
    deleted = await service.prune_stale_metrics(db_session, retention_days=30)
    assert deleted >= 1

    remaining = (await db_session.execute(select(SystemMetric))).scalars().all()
    assert any(m.cpu_percent == 15.0 for m in remaining)
    assert not any(m.cpu_percent == 55.0 for m in remaining)
