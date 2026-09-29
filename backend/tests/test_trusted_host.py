import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import create_app


@pytest.mark.asyncio
async def test_trusted_host_accepts_localhost() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1:8000", headers={"host": "127.0.0.1"}
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_trusted_host_rejects_untrusted_host() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    # Attempting to access with external or spoofed Host header
    async with AsyncClient(
        transport=transport,
        base_url="http://malicious-domain.com",
        headers={"host": "malicious-domain.com"},
    ) as client:
        response = await client.get("/health")
        # TrustedHostMiddleware returns 400 Bad Request for untrusted host
        assert response.status_code == 400
