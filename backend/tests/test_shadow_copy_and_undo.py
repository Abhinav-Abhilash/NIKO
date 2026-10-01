import pytest
from pathlib import Path
from httpx import AsyncClient

from backend.app.services.shadow_copy_service import ShadowCopyService
from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.undo_skill import UndoSkill


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def shadow_service(tmp_path: Path) -> ShadowCopyService:
    staging = tmp_path / "undo_staging"
    return ShadowCopyService(staging_dir=staging)


@pytest.fixture
async def owner_token_and_headers(db_session) -> dict[str, str]:
    from datetime import timedelta
    from backend.app.config import get_settings
    from backend.app.core.security import create_jwt_token, hash_password
    from backend.app.db.models import User

    owner = User(
        username="owner_undo_test",
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
async def test_shadow_copy_create_and_restore(temp_workspace: Path, shadow_service: ShadowCopyService) -> None:
    # 1. Create test file with original content
    test_file = temp_workspace / "important_document.txt"
    test_file.write_text("Original Content v1", encoding="utf-8")

    # 2. Take shadow snapshot before modification
    snap_id = shadow_service.create_snapshot([test_file], description="Pre-edit snapshot")
    assert snap_id.startswith("snap_")

    # 3. Simulate mutation: edit or delete file
    test_file.write_text("Destructive Overwrite v2", encoding="utf-8")
    assert test_file.read_text(encoding="utf-8") == "Destructive Overwrite v2"

    # 4. Restore snapshot
    res = shadow_service.restore_snapshot(snap_id)
    assert res["success"] is True
    assert res["restored_count"] == 1
    assert test_file.read_text(encoding="utf-8") == "Original Content v1"


@pytest.mark.asyncio
async def test_shadow_copy_restore_deleted_file(temp_workspace: Path, shadow_service: ShadowCopyService) -> None:
    test_file = temp_workspace / "deleted_file.txt"
    test_file.write_text("Keep Me Safe", encoding="utf-8")

    snap_id = shadow_service.create_snapshot([test_file], description="Pre-delete snapshot")

    # Delete the file
    test_file.unlink()
    assert not test_file.exists()

    # Restore
    res = shadow_service.restore_snapshot(snap_id)
    assert res["success"] is True
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "Keep Me Safe"


@pytest.mark.asyncio
async def test_shadow_copy_purge_expired(temp_workspace: Path, shadow_service: ShadowCopyService) -> None:
    test_file = temp_workspace / "old_doc.txt"
    test_file.write_text("Some text", encoding="utf-8")

    shadow_service.create_snapshot([test_file], description="Old snapshot")
    assert len(shadow_service.list_snapshots()) == 1

    # Purge with 0 hours max_age
    purged = shadow_service.purge_expired_snapshots(max_age_hours=0)
    assert purged == 1
    assert len(shadow_service.list_snapshots()) == 0


@pytest.mark.asyncio
async def test_undo_skill_manifest_and_execution(temp_workspace: Path, tmp_path: Path) -> None:
    from backend.app.services.shadow_copy_service import get_shadow_copy_service
    service = get_shadow_copy_service()
    service.staging_dir = tmp_path / "undo_staging"
    service.staging_dir.mkdir(parents=True, exist_ok=True)

    skill = UndoSkill()
    manifest = skill.manifest
    assert manifest.name == "undo"
    assert manifest.default_tier == "CONFIRM"

    # Create file and snapshot
    target_file = temp_workspace / "skill_test.txt"
    target_file.write_text("Hello Skill", encoding="utf-8")
    snap_id = service.create_snapshot([target_file], description="Skill test snapshot")

    target_file.write_text("Corrupted Text", encoding="utf-8")

    ctx = SkillContext(request_id="req_undo_1", user_id="user_123", provenance="direct")
    
    # 1. List snapshots action
    res_list = await skill.execute({"action": "list_snapshots"}, ctx)
    assert res_list.success is True
    assert res_list.data["total"] >= 1

    # 2. Undo last action
    res_undo = await skill.execute({"action": "undo_last"}, ctx)
    assert res_undo.success is True
    assert target_file.read_text(encoding="utf-8") == "Hello Skill"


@pytest.mark.asyncio
async def test_undo_rest_api(
    async_client: AsyncClient,
    owner_token_and_headers: dict[str, str],
    temp_workspace: Path,
    tmp_path: Path,
) -> None:
    from backend.app.services.shadow_copy_service import get_shadow_copy_service
    service = get_shadow_copy_service()
    service.staging_dir = tmp_path / "undo_staging"
    service.staging_dir.mkdir(parents=True, exist_ok=True)

    test_file = temp_workspace / "api_test.txt"
    test_file.write_text("API Initial Content", encoding="utf-8")
    snap_id = service.create_snapshot([test_file], description="API Snapshot")

    test_file.write_text("API Mutated Content", encoding="utf-8")

    # 1. Get snapshots
    res_get = await async_client.get("/api/v1/undo/snapshots", headers=owner_token_and_headers)
    assert res_get.status_code == 200
    assert res_get.json()["total"] >= 1

    # 2. Post revert
    res_revert = await async_client.post(
        "/api/v1/undo/revert",
        json={"snapshot_id": snap_id},
        headers=owner_token_and_headers,
    )
    assert res_revert.status_code == 200
    assert res_revert.json()["success"] is True
    assert test_file.read_text(encoding="utf-8") == "API Initial Content"
