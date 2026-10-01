import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token
from backend.app.db.models import User
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_schedules_api_flow(db_session: AsyncSession) -> None:
    settings = get_settings()

    # 1. Create authenticated owner user
    user = User(
        username="schedule_api_owner",
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
        # 1. POST /api/v1/schedules (Create interval task)
        create_resp = await client.post(
            "/api/v1/schedules",
            json={
                "name": "Database Backup Hook",
                "description": "Hourly snapshot of SQLite WAL",
                "schedule_type": "interval",
                "interval_seconds": 3600,
                "action_type": "skill",
                "action_name": "system_stats",
                "payload": {"backup": True},
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["name"] == "Database Backup Hook"
        assert data["status"] == "active"
        assert data["schedule_type"] == "interval"
        assert data["interval_seconds"] == 3600
        task_id = data["id"]

        # 2. GET /api/v1/schedules (List)
        list_resp = await client.get("/api/v1/schedules")
        assert list_resp.status_code == 200
        tasks = list_resp.json()
        assert len(tasks) >= 1
        assert any(t["id"] == task_id for t in tasks)

        # 3. GET /api/v1/schedules/{id} (Get Details)
        get_resp = await client.get(f"/api/v1/schedules/{task_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["id"] == task_id
        assert get_data["name"] == "Database Backup Hook"

        # 4. PATCH /api/v1/schedules/{id} (Pause and Update)
        patch_resp = await client.patch(
            f"/api/v1/schedules/{task_id}",
            json={
                "status": "paused",
                "interval_seconds": 7200,
            },
        )
        assert patch_resp.status_code == 200
        patched = patch_resp.json()
        assert patched["status"] == "paused"
        assert patched["interval_seconds"] == 7200

        # 5. DELETE /api/v1/schedules/{id} (Delete)
        del_resp = await client.delete(f"/api/v1/schedules/{task_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # 6. Verify subsequent GET returns 404
        missing_resp = await client.get(f"/api/v1/schedules/{task_id}")
        assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_schedules_api_requires_auth() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8000",
        headers={"Origin": "http://127.0.0.1:5173", "Host": "127.0.0.1:8000"},
    ) as client:
        resp = await client.get("/api/v1/schedules")
        assert resp.status_code == 401
