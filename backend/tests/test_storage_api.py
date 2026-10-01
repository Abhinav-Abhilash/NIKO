import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token
from backend.app.db.models import User
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_storage_api_flow(db_session: AsyncSession) -> None:
    settings = get_settings()

    user = User(
        username="storage_admin",
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
        # 1. GET /api/v1/storage/status
        status_resp = await client.get("/api/v1/storage/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert "database" in status_data
        assert "backups" in status_data
        assert "screenshots" in status_data
        assert "logs" in status_data

        # 2. POST /api/v1/storage/backup (Trigger online snapshot)
        backup_resp = await client.post("/api/v1/storage/backup")
        assert backup_resp.status_code == 200
        bdata = backup_resp.json()
        assert bdata["verified"] is True
        assert bdata["size_bytes"] > 0
        filename = bdata["filename"]

        # 3. GET /api/v1/storage/backups (List backups)
        list_resp = await client.get("/api/v1/storage/backups")
        assert list_resp.status_code == 200
        ldata = list_resp.json()
        assert ldata["count"] >= 1
        assert any(b["filename"] == filename for b in ldata["backups"])

        # 4. POST /api/v1/storage/maintenance (Trigger retention sweep)
        maint_resp = await client.post("/api/v1/storage/maintenance")
        assert maint_resp.status_code == 200
        mdata = maint_resp.json()
        assert mdata["status"] == "completed"

        # 5. DELETE /api/v1/storage/backups/{filename}
        del_resp = await client.delete(f"/api/v1/storage/backups/{filename}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # 6. DELETE path traversal attempt
        del_trav = await client.delete("/api/v1/storage/backups/..%2fescape.db")
        assert del_trav.status_code in (400, 404)
