import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "request_id" in data
    assert "storage" in data
    assert "free_gb" in data["storage"]

    # Verify X-Request-ID header is returned
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"] == data["request_id"]
