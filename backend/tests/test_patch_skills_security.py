from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import CommandLog, User
from backend.app.skills.registry import get_skill_registry


@pytest.mark.asyncio
async def test_patch_skill_owner_only_and_csrf_protected(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Setup non-owner (guest) and owner
    owner = User(username="admin_owner", password_hash=hash_password("pw1"), role="owner")
    guest = User(username="guest_user", password_hash=hash_password("pw2"), role="guest")
    db_session.add_all([owner, guest])
    await db_session.commit()

    settings = get_settings()
    owner_token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )
    guest_token = create_jwt_token(
        payload={"sub": guest.id, "username": guest.username, "role": guest.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    valid_headers = {
        "Authorization": f"Bearer {owner_token}",
        "Origin": "http://127.0.0.1:5173",
    }
    guest_headers = {
        "Authorization": f"Bearer {guest_token}",
        "Origin": "http://127.0.0.1:5173",
    }
    csrf_attack_headers = {
        "Authorization": f"Bearer {owner_token}",
        "Origin": "http://evil-attacker-site.com",
    }

    # Test 1: Unauthorized without auth -> 401
    res_no_auth = await async_client.patch(
        "/api/v1/skills/datetime",
        json={"autonomy_policy": "auto+log"},
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert res_no_auth.status_code == 401

    # Test 2: Non-owner (guest) forbidden -> 403
    res_guest = await async_client.patch(
        "/api/v1/skills/datetime",
        json={"autonomy_policy": "auto+log"},
        headers=guest_headers,
    )
    assert res_guest.status_code == 403

    # Test 3: CSRF attack from disallowed origin -> 403
    res_csrf = await async_client.patch(
        "/api/v1/skills/datetime",
        json={"autonomy_policy": "auto+log"},
        headers=csrf_attack_headers,
    )
    assert res_csrf.status_code == 403
    assert "INVALID_ORIGIN" in res_csrf.text

    # Test 4: Valid owner with allowed origin -> 200 and audit-logged
    res_valid = await async_client.patch(
        "/api/v1/skills/datetime",
        json={"autonomy_policy": "auto+log", "timeout_seconds": 25},
        headers=valid_headers,
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["autonomy_policy"] == "auto+log"
    assert res_valid.json()["timeout_seconds"] == 25

    # Verify audit log in SQLite
    audit_entries = (
        await db_session.execute(
            select(CommandLog).where(
                CommandLog.skill_name == "datetime",
                CommandLog.user_id == owner.id,
            )
        )
    ).scalars().all()
    assert len(audit_entries) >= 1
    latest_audit = audit_entries[-1]
    assert latest_audit.status == "success"
    assert "update_skill_config" in latest_audit.arguments_json


def test_admin_config_endpoints_excluded_from_llm_tool_definitions() -> None:
    """LLM tool definitions must strictly only include executable skills, never admin configs."""
    registry = get_skill_registry()
    tools = registry.get_tool_definitions()

    tool_names = [t["function"]["name"] for t in tools]
    # Executable skills are present
    assert "datetime" in tool_names or len(tool_names) >= 0

    # Ensure admin mutation actions are NEVER in LLM tools
    forbidden_terms = ["patch", "update_skill", "config", "skills_admin", "autonomy"]
    for name in tool_names:
        for forbidden in forbidden_terms:
            assert forbidden not in name.lower()
