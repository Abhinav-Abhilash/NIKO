from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import User
from backend.app.llm.types import ModelRolesConfig, RoleModelTarget


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
async def test_get_and_put_model_roles(
    async_client: AsyncClient, owner_token_and_headers: dict[str, str]
) -> None:
    # 1. Get default model roles
    res = await async_client.get("/api/v1/settings/roles", headers=owner_token_and_headers)
    assert res.status_code == 200
    data = res.json()
    assert "light" in data
    assert "chat" in data
    assert "code" in data
    assert "search" in data
    assert data["light"][0]["provider"] == "groq"
    assert data["light"][0]["model"] == "openai/gpt-oss-20b"

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

    put_res = await async_client.put(
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
    get_res2 = await async_client.get("/api/v1/settings/roles", headers=owner_token_and_headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["light"][0]["model"] == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_models_status_and_refresh(
    async_client: AsyncClient, owner_token_and_headers: dict[str, str]
) -> None:
    # Check status
    status_res = await async_client.get("/api/v1/settings/models/status", headers=owner_token_and_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "discovered" in status_data
    assert "quotas" in status_data
    assert "roles" in status_data

    # Refresh with mocked discovery to prevent external network calls
    with patch(
        "backend.app.llm.discovery.model_discovery.refresh_all", new_callable=AsyncMock
    ) as mock_refresh:
        mock_refresh.return_value = {
            "gemini": ["gemini-2.0-flash"],
            "groq": ["llama-3.3-70b-versatile"],
            "openrouter": ["openrouter/free"],
        }
        refresh_res = await async_client.post(
            "/api/v1/settings/models/refresh", headers=owner_token_and_headers
        )
        assert refresh_res.status_code == 200
        refresh_data = refresh_res.json()
        assert refresh_data["status"] == "refreshed"
        assert "discovered_models" in refresh_data


@pytest.mark.asyncio
async def test_get_and_put_shell_hotkey(
    async_client: AsyncClient, owner_token_and_headers: dict[str, str]
) -> None:
    # 1. Get default hotkey
    res = await async_client.get("/api/v1/settings/hotkey", headers=owner_token_and_headers)
    assert res.status_code == 200
    assert res.json()["hotkey"] == "Ctrl+Space"

    # 2. Update to a new valid combination
    put_res = await async_client.put(
        "/api/v1/settings/hotkey",
        headers=owner_token_and_headers,
        json={"hotkey": "Alt+Space"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["hotkey"] == "Alt+Space"

    # 3. Verify persistence
    get_res2 = await async_client.get("/api/v1/settings/hotkey", headers=owner_token_and_headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["hotkey"] == "Alt+Space"


@pytest.mark.asyncio
async def test_put_shell_hotkey_validation_and_security(
    async_client: AsyncClient, owner_token_and_headers: dict[str, str]
) -> None:
    # 1. Empty hotkey rejected
    res_empty = await async_client.put(
        "/api/v1/settings/hotkey",
        headers=owner_token_and_headers,
        json={"hotkey": ""},
    )
    assert res_empty.status_code == 422

    # 2. Single key without modifier rejected
    res_single = await async_client.put(
        "/api/v1/settings/hotkey",
        headers=owner_token_and_headers,
        json={"hotkey": "K"},
    )
    assert res_single.status_code == 422

    # 3. Unauthorized request without auth header rejected
    res_unauth = await async_client.get("/api/v1/settings/hotkey")
    assert res_unauth.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_and_put_pet_persona(
    async_client: AsyncClient, owner_token_and_headers: dict[str, str]
) -> None:
    # 1. Get default persona
    res = await async_client.get("/api/v1/settings/persona", headers=owner_token_and_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "NIKO"
    assert "companion" in data["persona"].lower()

    # 2. Update persona
    put_res = await async_client.put(
        "/api/v1/settings/persona",
        headers=owner_token_and_headers,
        json={"name": "NIKO PRO", "persona": "A super intelligent AI sidekick."},
    )
    assert put_res.status_code == 200
    put_data = put_res.json()
    assert put_data["name"] == "NIKO PRO"
    assert put_data["persona"] == "A super intelligent AI sidekick."

    # 3. Verify persistence
    get_res2 = await async_client.get("/api/v1/settings/persona", headers=owner_token_and_headers)
    assert get_res2.status_code == 200
    assert get_res2.json()["name"] == "NIKO PRO"


