import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password
from backend.app.db.models import User
from backend.app.services.auth_service import login_limiter


@pytest.mark.asyncio
async def test_auth_login_me_refresh_and_logout(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. Seed a user
    user = User(
        username="niko_admin",
        password_hash=hash_password("SuperSecurePassword123!"),
        role="owner",
    )
    db_session.add(user)
    await db_session.commit()

    # 2. Login successfully
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "niko_admin", "password": "SuperSecurePassword123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["username"] == "niko_admin"
    assert "access_token" in data
    access_token = data["access_token"]

    # Verify cookies
    assert "niko_access_token" in login_res.cookies
    assert "niko_refresh_token" in login_res.cookies
    refresh_token = login_res.cookies["niko_refresh_token"]

    # 3. Access protected /me endpoint
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "niko_admin"

    # 4. Refresh token rotation
    async_client.cookies.set("niko_refresh_token", refresh_token)
    refresh_res = await async_client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    new_refresh_token = refresh_res.cookies["niko_refresh_token"]
    assert new_refresh_token != refresh_token  # Token rotated

    # 5. Reuse detection: presenting the old revoked refresh token MUST fail and trigger family revocation
    async_client.cookies.set("niko_refresh_token", refresh_token)
    reuse_res = await async_client.post("/api/v1/auth/refresh")
    assert reuse_res.status_code == 401
    assert "reused" in reuse_res.json()["error"]["message"]

    # 6. Logout
    async_client.cookies.set("niko_refresh_token", new_refresh_token)
    logout_res = await async_client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200


@pytest.mark.asyncio
async def test_login_rate_limiting_exponential_backoff(async_client: AsyncClient) -> None:
    # Reset limiter for clean test
    login_limiter._history.clear()

    # Attempts 1 to 3: return 401 Unauthorized (not rate limited)
    for _ in range(3):
        res = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "target_user", "password": "wrong_password"},
        )
        assert res.status_code == 401

    # Attempt 4: fails and triggers 2s backoff lockout
    res_4 = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "target_user", "password": "wrong_password"},
    )
    assert res_4.status_code == 401

    # Immediate next attempt triggers 429 RATE_LIMIT_EXCEEDED
    res_locked = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "target_user", "password": "wrong_password"},
    )
    assert res_locked.status_code == 429
    assert res_locked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
