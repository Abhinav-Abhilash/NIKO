from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token
from backend.app.db.models import Reminder, User
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_reminders_api_flow(db_session: AsyncSession) -> None:
    settings = get_settings()

    # 1. Create authenticated user
    user = User(
        username="reminder_api_owner",
        password_hash="fake_hash",
        role="owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_jwt_token(
        {"sub": user.id, "username": user.username, "role": user.role},
        secret_key=settings.JWT_SECRET_KEY,
    )

    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8000",
        cookies={"niko_access_token": token},
        headers={"Origin": "http://127.0.0.1:5173", "Host": "127.0.0.1:8000"},
    ) as client:
        # 1. POST /api/v1/reminders (Create)
        future_trigger = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        create_resp = await client.post(
            "/api/v1/reminders",
            json={
                "title": "Team Standup",
                "description": "Daily sync meeting",
                "trigger_at": future_trigger,
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["title"] == "Team Standup"
        assert data["status"] == "scheduled"
        reminder_id = data["id"]

        # 2. GET /api/v1/reminders (List)
        list_resp = await client.get("/api/v1/reminders?status=scheduled")
        assert list_resp.status_code == 200
        reminders = list_resp.json()
        assert len(reminders) >= 1
        assert any(r["id"] == reminder_id for r in reminders)

        # 3. DELETE /api/v1/reminders/{id} (Cancel)
        cancel_resp = await client.delete(f"/api/v1/reminders/{reminder_id}")
        assert cancel_resp.status_code == 200
        cancelled_data = cancel_resp.json()
        assert cancelled_data["status"] == "cancelled"
