import sys
from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.app.services.mcp_service import (
    MCPServerConfig,
    MCPService,
)
from backend.app.skills.base import SkillContext
from backend.app.skills.registry import SkillRegistry

# Minimal mock python script acting as an MCP stdio server
MOCK_MCP_SERVER_CODE = """
import sys
import json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    try:
        msg = json.loads(line)
        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"}
                }
            }
            sys.stdout.write(json.dumps(res) + "\\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "calc_add",
                            "description": "Add two integers together",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "a": {"type": "integer"},
                                    "b": {"type": "integer"}
                                },
                                "required": ["a", "b"]
                            }
                        }
                    ]
                }
            }
            sys.stdout.write(json.dumps(res) + "\\n")
            sys.stdout.flush()

        elif method == "tools/call":
            params = msg.get("params", {})
            args = params.get("arguments", {})
            a = args.get("a", 0)
            b = args.get("b", 0)
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": str(a + b)}]
                }
            }
            sys.stdout.write(json.dumps(res) + "\\n")
            sys.stdout.flush()

    except Exception as e:
        pass
"""


@pytest.fixture
def mock_mcp_script(tmp_path: Path) -> Path:
    script_file = tmp_path / "mock_mcp_server.py"
    script_file.write_text(MOCK_MCP_SERVER_CODE, encoding="utf-8")
    return script_file


@pytest.fixture
async def owner_token_and_headers(db_session) -> dict[str, str]:
    from datetime import timedelta

    from backend.app.config import get_settings
    from backend.app.core.security import create_jwt_token, hash_password
    from backend.app.db.models import User

    owner = User(
        username="owner_mcp_test",
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
async def test_mcp_client_stdio_handshake_and_execution(mock_mcp_script: Path) -> None:
    config = MCPServerConfig(
        name="test_math",
        command=sys.executable,
        args=[str(mock_mcp_script)],
        tier="CONFIRM",
        autonomy="ask",
        timeout_seconds=5,
    )

    registry = SkillRegistry()
    service = MCPService(registry=registry)

    try:
        registered = await service.start_server(config)
        assert len(registered) == 1
        assert registered[0] == "mcp__test_math__calc_add"
        assert registry.has("mcp__test_math__calc_add")

        skill = registry.get("mcp__test_math__calc_add")
        manifest = skill.manifest
        assert manifest.name == "mcp__test_math__calc_add"
        assert manifest.default_tier == "CONFIRM"
        assert manifest.default_autonomy == "ask"
        assert "[MCP: test_math]" in manifest.description
        assert "properties" in manifest.parameters_schema

        # Execute tool call
        ctx = SkillContext(request_id="req_mcp_1", user_id="user_123", provenance="direct")
        res = await skill.execute({"a": 12, "b": 30}, ctx)
        assert res.success is True
        assert res.data == [{"type": "text", "text": "42"}]

    finally:
        await service.stop_server("test_math")
        assert not registry.has("mcp__test_math__calc_add")


@pytest.mark.asyncio
async def test_mcp_rest_api_crud(
    async_client: AsyncClient,
    owner_token_and_headers: dict[str, str],
    tmp_path: Path,
    mock_mcp_script: Path,
) -> None:
    config_file = tmp_path / "mcp_servers.json"
    from backend.app.services.mcp_service import get_mcp_service
    service = get_mcp_service()
    service.config_path = config_file

    try:
        # 1. Register server
        payload = {
            "name": "mock_api_server",
            "command": sys.executable,
            "args": [str(mock_mcp_script)],
            "tier": "CONFIRM",
            "autonomy": "ask",
            "enabled": True,
            "timeout_seconds": 5,
        }
        res_post = await async_client.post(
            "/api/v1/mcp/servers",
            json=payload,
            headers=owner_token_and_headers,
        )
        assert res_post.status_code == 200
        data_post = res_post.json()
        assert data_post["success"] is True

        # 2. List servers
        res_list = await async_client.get(
            "/api/v1/mcp/servers",
            headers=owner_token_and_headers,
        )
        assert res_list.status_code == 200
        servers = res_list.json()["servers"]
        assert len(servers) >= 1
        assert any(s["name"] == "mock_api_server" for s in servers)

        # 3. List tools
        res_tools = await async_client.get(
            "/api/v1/mcp/tools",
            headers=owner_token_and_headers,
        )
        assert res_tools.status_code == 200
        tools = res_tools.json()["tools"]
        assert any(t["tool_name"] == "calc_add" for t in tools)

        # 4. Stop and delete server
        res_del = await async_client.delete(
            "/api/v1/mcp/servers/mock_api_server",
            headers=owner_token_and_headers,
        )
        assert res_del.status_code == 200
        assert res_del.json()["success"] is True
    finally:
        await service.stop_server("mock_api_server")
