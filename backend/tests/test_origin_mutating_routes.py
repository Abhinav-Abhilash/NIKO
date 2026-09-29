import json
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token, hash_password
from backend.app.db.models import ToolCall, User
from backend.app.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_approvals_respond_route_rejects_unauthorized_origin(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Setup owner
    owner = User(
        username="owner_csrf_test",
        password_hash=hash_password("password_123"),
        role="owner",
    )
    db_session.add(owner)
    await db_session.flush()

    settings = get_settings()
    access_token = create_jwt_token(
        payload={"sub": owner.id, "username": owner.username, "role": owner.role},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    # 2. Setup pending approval
    args = {"target": "calc.exe"}
    tool_call = ToolCall(
        skill_name="open_app",
        arguments_json=json.dumps(args),
        status="awaiting_approval",
    )
    db_session.add(tool_call)
    await db_session.flush()

    service = ApprovalService(db_session)
    approval = await service.create_approval(
        tool_call_id=tool_call.id,
        arguments=args,
        skill_name="open_app",
    )
    await db_session.commit()

    # 3. Post response with unauthorized origin -> 403 Forbidden
    evil_headers = {
        "Authorization": f"Bearer {access_token}",
        "Origin": "http://evil-attacker-site.com",
    }
    evil_res = await async_client.post(
        f"/api/v1/approvals/{approval.id}/respond",
        headers=evil_headers,
        json={"decision": "approve", "arguments": args},
    )
    assert evil_res.status_code == 403
    assert evil_res.json()["error"]["code"] == "INVALID_ORIGIN"

    # 4. Post response with authorized localhost origin -> 200 OK
    good_headers = {
        "Authorization": f"Bearer {access_token}",
        "Origin": "http://localhost:5173",
    }
    good_res = await async_client.post(
        f"/api/v1/approvals/{approval.id}/respond",
        headers=good_headers,
        json={"decision": "approve", "arguments": args},
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "approved"
