from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import User
from backend.app.services.memory_service import MemoryService


@pytest.fixture
async def owner_headers(db_session: AsyncSession) -> dict[str, str]:
    owner = User(
        username="owner_mem_api",
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
async def test_memory_config_api(
    async_client: AsyncClient, owner_headers: dict[str, str]
) -> None:
    # 1. Get default config
    res = await async_client.get("/api/v1/memories/config", headers=owner_headers)
    assert res.status_code == 200
    cfg = res.json()
    assert cfg["mode"] == "auto"
    assert cfg["enabled"] is True

    # 2. Update config to suggest mode and disable
    put_res = await async_client.put(
        "/api/v1/memories/config",
        headers=owner_headers,
        json={"mode": "suggest", "enabled": False},
    )
    assert put_res.status_code == 200
    updated_cfg = put_res.json()
    assert updated_cfg["mode"] == "suggest"
    assert updated_cfg["enabled"] is False

    # 3. Re-enable and reset to auto
    reset_res = await async_client.put(
        "/api/v1/memories/config",
        headers=owner_headers,
        json={"mode": "auto", "enabled": True},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["mode"] == "auto"
    assert reset_res.json()["enabled"] is True


@pytest.mark.asyncio
async def test_memory_crud_and_export_api(
    async_client: AsyncClient, owner_headers: dict[str, str], db_session: AsyncSession
) -> None:
    from sqlalchemy import select
    res_user = await db_session.execute(select(User).where(User.username == "owner_mem_api"))
    owner = res_user.scalar_one()

    # Seed memories directly via MemoryService
    service = MemoryService(db_session)
    res1 = await service.remember(
        user_id=owner.id,
        content="Prefers dark roast coffee with a splash of oat milk.",
        key="coffee_pref",
        category="preference",
        pinned=True,
    )
    assert res1["saved"] is True
    mem_id = res1["memory_id"]

    res2 = await service.remember(
        user_id=owner.id,
        content="Favorite programming language is Python and TypeScript.",
        key="prog_lang",
        category="work",
    )
    assert res2["saved"] is True
    await db_session.commit()

    # 1. List all memories
    list_res = await async_client.get("/api/v1/memories", headers=owner_headers)
    assert list_res.status_code == 200
    memories = list_res.json()
    assert len(memories) >= 2

    # 2. Search memories by query
    search_res = await async_client.get("/api/v1/memories?query=coffee", headers=owner_headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data) >= 1
    assert search_data[0]["key"] == "coffee_pref"

    # 3. Filter by category
    cat_res = await async_client.get("/api/v1/memories?category=work", headers=owner_headers)
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert any(m["key"] == "prog_lang" for m in cat_data)

    # 4. Get single memory detail
    detail_res = await async_client.get(f"/api/v1/memories/{mem_id}", headers=owner_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == mem_id
    assert detail_res.json()["pinned"] is True

    # 5. Edit memory
    edit_res = await async_client.put(
        f"/api/v1/memories/{mem_id}",
        headers=owner_headers,
        json={"content": "Prefers medium roast Ethiopian coffee with oat milk.", "category": "food"},
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["category"] == "food"
    assert "Ethiopian" in edit_res.json()["content"]

    # 6. Export memories
    export_res = await async_client.get("/api/v1/memories/export", headers=owner_headers)
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert isinstance(export_data, list)
    assert len(export_data) >= 2

    # 7. Delete memory
    del_res = await async_client.delete(f"/api/v1/memories/{mem_id}", headers=owner_headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 8. Verify 404 after deletion
    after_del = await async_client.get(f"/api/v1/memories/{mem_id}", headers=owner_headers)
    assert after_del.status_code == 404
