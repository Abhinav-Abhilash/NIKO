from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import User
from backend.app.llm.types import ModelRolesConfig, RoleModelTarget
from backend.app.main import app


@pytest.fixture
async def owner_token_and_headers(db_session: AsyncSession) -> dict[str, str]:
    owner = User(
        username="owner_settings",
        password_hash=hash_password("SuperSecret123!"),
        role="owner",
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    settings = get_settings()
    token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )
    return {
        "Authorization": f"Bearer {token}",
        "Origin": "http://127.0.0.1:5173",
        "X-CSRF-Token": "test-csrf",
    }


@pytest.mark.asyncio
async def test_get_and_put_model_roles(owner_token_and_headers: dict[str, str]) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        # 1. Get default model roles
        res = await client.get("/api/v1/settings/roles", headers=owner_token_and_headers)
        assert res.status_code == 200
        data = res.json()
        assert "light" in data
        assert "chat" in data
        assert "code" in data
        assert "search" in data
        assert len(data["light"]) >= 2
        assert data["light"][0]["provider"] == "gemini"

        # 2. Update model roles
        custom_config = ModelRolesConfig(
            light=[
                RoleModelTarget(
                    provider="groq",
                    model="openai/gpt-oss-20b",
                    max_output_tokens=512,
                    reasoning_effort="low",
                )
            ],
            chat=[
                RoleModelTarget(
                    provider="groq",
                    model="openai/gpt-oss-120b",
                    max_output_tokens=2048,
                    reasoning_effort="default",
                )
            ],
            code=[],
            search=[],
        )

        put_res = await client.put(
            "/api/v1/settings/roles",
            headers=owner_token_and_headers,
            json=custom_config.model_dump(),
        )
        assert put_res.status_code == 200
        put_data = put_res.json()
        assert len(put_data["light"]) == 1
        assert put_data["light"][0]["provider"] == "groq"
        assert put_data["light"][0]["max_output_tokens"] == 512

        # 3. Verify persistence on subsequent GET
        get_res2 = await client.get("/api/v1/settings/roles", headers=owner_token_and_headers)
        assert get_res2.status_code == 200
        assert get_res2.json()["light"][0]["model"] == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_models_status_and_refresh(owner_token_and_headers: dict[str, str]) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        # Check status
        status_res = await client.get("/api/v1/settings/models/status", headers=owner_token_and_headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "discovered" in status_data
        assert "quotas" in status_data

        # Refresh
        refresh_res = await client.post("/api/v1/settings/models/refresh", headers=owner_token_and_headers)
        assert refresh_res.status_code == 200
        refresh_data = refresh_res.json()
        assert refresh_data["status"] == "refreshed"
        assert "discovered_models" in refresh_data
