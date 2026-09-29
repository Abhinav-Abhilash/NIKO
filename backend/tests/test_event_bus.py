import asyncio

import pytest

from backend.app.core.events import EventBus


@pytest.mark.asyncio
async def test_event_bus_publish_and_subscribe() -> None:
    bus = EventBus(maxsize=100)
    received_events = []

    async def reader() -> None:
        async for event in bus.subscribe(topic="sys:metrics"):
            received_events.append(event)
            if len(received_events) >= 2:
                break

    task = asyncio.create_task(reader())
    await asyncio.sleep(0.01)

    # Publish events
    await bus.publish("sys:metrics", "cpu", {"cpu_percent": 15.2})
    await bus.publish("chat:stream", "chunk", {"text": "hello"})  # Should be ignored by subscriber
    await bus.publish("sys:metrics", "ram", {"ram_percent": 42.0})

    await asyncio.wait_for(task, timeout=2.0)

    assert len(received_events) == 2
    assert received_events[0].topic == "sys:metrics"
    assert received_events[0].payload["cpu_percent"] == 15.2
    assert received_events[1].payload["ram_percent"] == 42.0


@pytest.mark.asyncio
async def test_event_bus_global_subscription() -> None:
    bus = EventBus(maxsize=100)
    received = []

    async def global_reader() -> None:
        async for event in bus.subscribe(topic=None):  # All topics
            received.append(event)
            if len(received) >= 2:
                break

    task = asyncio.create_task(global_reader())
    await asyncio.sleep(0.01)

    await bus.publish("topic_a", "type_1", {"msg": "a"})
    await bus.publish("topic_b", "type_2", {"msg": "b"})

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received) == 2
    assert received[0].topic == "topic_a"
    assert received[1].topic == "topic_b"
