import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.config import get_settings
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_first_boot_onboarding_and_barrier_e2e() -> None:
    """
    End-to-End simulation of clean-machine first boot:
    1. Unauthenticated requests are rejected (401).
    2. Invalid setup_token in /auth/setup is rejected (400).
    3. Valid setup_token initializes the first owner user.
    4. Subsequent setup attempts are strictly blocked.
    5. Owner user can seamlessly access protected assistant resources.
    """
    settings = get_settings()
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8000",
        headers={"Origin": "http://127.0.0.1:5173", "Host": "127.0.0.1:8000"},
    ) as client:
        # 1. Unauthenticated request to /auth/me returns 401
        me_unauth = await client.get("/api/v1/auth/me")
        assert me_unauth.status_code == 401

        # 2. Attempt setup with wrong setup token -> 401 (Invalid setup token)
        bad_setup = await client.post(
            "/api/v1/auth/setup",
            json={
                "username": "first_boot_owner",
                "password": "Password123!Secure",
                "setup_token": "INVALID_TOKEN_12345",
            },
        )
        assert bad_setup.status_code == 401
        err_msg = bad_setup.json().get("error", {}).get("message", "") or bad_setup.json().get("detail", "")
        assert "setup token" in err_msg.lower()

        # 3. Valid setup token -> 200 OK + Owner created
        valid_setup = await client.post(
            "/api/v1/auth/setup",
            json={
                "username": "first_boot_owner",
                "password": "Password123!Secure",
                "setup_token": settings.SETUP_TOKEN,
            },
        )
        assert valid_setup.status_code == 200
        sdata = valid_setup.json()
        assert sdata["username"] == "first_boot_owner"
        assert sdata["role"] == "owner"

        # 4. Attempt second setup -> strictly blocked (SetupForbiddenError)
        second_setup = await client.post(
            "/api/v1/auth/setup",
            json={
                "username": "imposter_owner",
                "password": "Password123!Hacker",
                "setup_token": settings.SETUP_TOKEN,
            },
        )
        assert second_setup.status_code in (400, 403)
        err_msg2 = second_setup.json().get("error", {}).get("message", "") or second_setup.json().get("detail", "")
        assert "initialized" in err_msg2.lower()

        # 5. Login as the newly created owner -> 200 OK + Cookies set
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "first_boot_owner",
                "password": "Password123!Secure",
            },
        )
        assert login_resp.status_code == 200
        assert "niko_access_token" in login_resp.cookies
        access_cookie = login_resp.cookies["niko_access_token"]
        client.cookies.set("niko_access_token", access_cookie)

        # 5. Authenticated owner accesses /auth/me
        me_auth = await client.get("/api/v1/auth/me")
        assert me_auth.status_code == 200
        assert me_auth.json()["username"] == "first_boot_owner"

        # 6. Authenticated owner accesses storage status
        storage_resp = await client.get("/api/v1/storage/status")
        assert storage_resp.status_code == 200
        assert "database" in storage_resp.json()
