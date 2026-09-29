from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import User


async def _create_test_owner(db_session: AsyncSession) -> tuple[User, dict[str, str]]:
    owner = User(
        username="owner_api_test",
        password_hash=hash_password("owner_password_123"),
        role="owner",
    )
    db_session.add(owner)
    await db_session.commit()

    settings = get_settings()
    token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=30),
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "http://127.0.0.1:5173",
    }
    return owner, headers


@pytest.mark.asyncio
async def test_skills_api_list_and_update(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, headers = await _create_test_owner(db_session)

    # 1. List skills
    res = await async_client.get("/api/v1/skills", headers=headers)
    assert res.status_code == 200
    skills = res.json()
    assert isinstance(skills, list)
    skill_names = [s["name"] for s in skills]
    assert "datetime" in skill_names
    assert "system_stats" in skill_names

    # 2. Patch skill autonomy policy to 'ask'
    patch_res = await async_client.patch(
        "/api/v1/skills/datetime",
        json={"autonomy_policy": "ask", "timeout_seconds": 10},
        headers=headers,
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["autonomy_policy"] == "ask"
    assert patched["timeout_seconds"] == 10

    # 3. Execute datetime under 'ask' -> triggers confirmation required
    exec_res = await async_client.post(
        "/api/v1/skills/datetime/execute",
        json={"arguments": {}, "provenance": "direct"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["success"] is False
    assert exec_data["error"] == "CONFIRMATION_REQUIRED"
    assert "approval_id" in exec_data["data"]

    # 4. Patch back to 'auto'
    patch_back = await async_client.patch(
        "/api/v1/skills/datetime",
        json={"autonomy_policy": "auto"},
        headers=headers,
    )
    assert patch_back.status_code == 200
    assert patch_back.json()["autonomy_policy"] == "auto"

    # 5. Execute datetime under 'auto' -> executes immediately
    exec_ok = await async_client.post(
        "/api/v1/skills/datetime/execute",
        json={"arguments": {}, "provenance": "direct"},
        headers=headers,
    )
    assert exec_ok.status_code == 200
    data: dict[str, Any] = exec_ok.json()
    assert data["success"] is True
    assert "iso_local" in data["data"]


@pytest.mark.asyncio
async def test_metrics_api_endpoints(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, headers = await _create_test_owner(db_session)

    # 1. GET current metrics
    res_current = await async_client.get("/api/v1/metrics/current", headers=headers)
    assert res_current.status_code == 200
    current_data = res_current.json()
    assert "cpu_percent" in current_data
    assert "ram_percent" in current_data
    assert "disk_percent" in current_data

    # 2. POST tab visibility hidden -> toggles to 15s cadence
    res_vis_hidden = await async_client.post(
        "/api/v1/metrics/visibility",
        json={"hidden": True},
        headers=headers,
    )
    assert res_vis_hidden.status_code == 200
    assert res_vis_hidden.json()["hidden"] is True
    assert res_vis_hidden.json()["interval_seconds"] == 15.0

    # 3. POST tab visibility visible -> restores 2s cadence
    res_vis_active = await async_client.post(
        "/api/v1/metrics/visibility",
        json={"hidden": False},
        headers=headers,
    )
    assert res_vis_active.status_code == 200
    assert res_vis_active.json()["hidden"] is False
    assert res_vis_active.json()["interval_seconds"] == 2.0

    # 4. GET historical metrics
    res_hist = await async_client.get("/api/v1/metrics/history", headers=headers)
    assert res_hist.status_code == 200
    assert isinstance(res_hist.json(), list)
