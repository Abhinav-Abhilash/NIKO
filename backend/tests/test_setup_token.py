import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_setup_token_flow(async_client: AsyncClient) -> None:
    # 1. Attempt setup with invalid token -> 401
    invalid_res = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "username": "owner",
            "password": "supersecurepassword123",
            "setup_token": "wrong_token",
        },
    )
    assert invalid_res.status_code == 401
    assert invalid_res.json()["error"]["code"] == "INVALID_SETUP_TOKEN"

    # 2. Attempt setup with correct token -> 200 Created
    valid_res = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "username": "niko_owner",
            "password": "supersecurepassword123",
            "setup_token": "test_setup_token_12345",
        },
    )
    assert valid_res.status_code == 200
    data = valid_res.json()
    assert data["username"] == "niko_owner"
    assert data["role"] == "owner"
    assert len(data["providers_initialized"]) > 0

    # 3. Attempt setup again -> 403 Forbidden (Already completed)
    second_res = await async_client.post(
        "/api/v1/auth/setup",
        json={
            "username": "attacker",
            "password": "anotherpassword123",
            "setup_token": "test_setup_token_12345",
        },
    )
    assert second_res.status_code == 403
    assert second_res.json()["error"]["code"] == "SETUP_ALREADY_COMPLETED"
