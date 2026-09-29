from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import CommandLog, SystemMetric, User


@pytest.mark.asyncio
async def test_utcdatetime_preserves_utc_awareness_on_models(db_session: AsyncSession) -> None:
    # 1. User with TimestampMixin (created_at, updated_at)
    user = User(username="utc_test_user", password_hash="hashed_pw", role="owner")
    db_session.add(user)

    # 2. CommandLog with created_at explicitly set to an offset-aware datetime (IST = UTC+5:30)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ist_time = datetime(2026, 9, 29, 15, 30, 0, tzinfo=ist_tz)
    log = CommandLog(
        request_id="req_utc_test",
        skill_name="test_skill",
        permission_tier="SAFE",
        provenance="direct",
        arguments_json="{}",
        status="success",
        created_at=ist_time,
    )
    db_session.add(log)

    # 3. SystemMetric with naive datetime (simulating naive timestamp input)
    naive_time = datetime(2026, 9, 29, 10, 0, 0)
    metric = SystemMetric(
        cpu_percent=12.5,
        ram_percent=45.0,
        disk_percent=33.3,
        timestamp=naive_time,
    )
    db_session.add(metric)
    await db_session.commit()
    db_session.expire_all()

    # Query back and verify all loaded datetimes have UTC tzinfo
    loaded_user = (await db_session.execute(select(User).where(User.username == "utc_test_user"))).scalar_one()
    assert loaded_user.created_at.tzinfo is not None
    assert loaded_user.created_at.tzinfo == UTC
    assert loaded_user.updated_at.tzinfo == UTC

    loaded_log = (await db_session.execute(select(CommandLog).where(CommandLog.request_id == "req_utc_test"))).scalar_one()
    assert loaded_log.created_at.tzinfo == UTC
    # 15:30 IST is 10:00 UTC
    assert loaded_log.created_at.hour == 10
    assert loaded_log.created_at.minute == 0

    loaded_metric = (await db_session.execute(select(SystemMetric))).scalar_one()
    assert loaded_metric.timestamp.tzinfo == UTC
    assert loaded_metric.timestamp.hour == 10
