from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.db.models import User
from backend.app.dependencies import get_current_user
from backend.app.services.mcp_service import MCPServerConfig, get_mcp_service

router = APIRouter(prefix="/mcp", tags=["MCP Extensibility"])


@router.get("/servers")
async def list_mcp_servers(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """List all registered MCP servers and their current runtime status."""
    service = get_mcp_service()
    configs = service.load_configs()
    result = []
    for name, cfg in configs.items():
        is_running = name in service.clients and service.clients[name].process is not None
        registered_tools = service.registered_skills.get(name, [])
        result.append({
            **cfg.model_dump(),
            "is_running": is_running,
            "tools_count": len(registered_tools),
            "tools": registered_tools,
        })
    return {"servers": result}


@router.post("/servers")
async def create_or_update_mcp_server(
    config: MCPServerConfig,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Register or update an MCP server configuration."""
    service = get_mcp_service()
    configs = service.load_configs()
    configs[config.name] = config
    service.save_configs(configs)

    registered_tools: list[str] = []
    if config.enabled:
        try:
            registered_tools = await service.start_server(config)
        except Exception as exc:
            return {
                "success": True,
                "message": f"Saved config, but failed to start server: {exc}",
                "config": config.model_dump(),
                "tools": [],
            }

    return {
        "success": True,
        "config": config.model_dump(),
        "tools": registered_tools,
    }


@router.delete("/servers/{server_name}")
async def delete_mcp_server(
    server_name: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete an MCP server configuration and stop its process."""
    service = get_mcp_service()
    configs = service.load_configs()
    if server_name not in configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Server '{server_name}' not found.",
        )

    await service.stop_server(server_name)
    del configs[server_name]
    service.save_configs(configs)
    return {"success": True, "message": f"MCP server '{server_name}' removed."}


@router.post("/servers/{server_name}/start")
async def start_mcp_server(
    server_name: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Start an MCP server and register its dynamic tools."""
    service = get_mcp_service()
    configs = service.load_configs()
    if server_name not in configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Server '{server_name}' not found.",
        )

    try:
        tools = await service.start_server(configs[server_name])
        return {"success": True, "server": server_name, "tools": tools}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start MCP server '{server_name}': {exc}",
        ) from exc


@router.post("/servers/{server_name}/stop")
async def stop_mcp_server(
    server_name: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Stop an MCP server process."""
    service = get_mcp_service()
    await service.stop_server(server_name)
    return {"success": True, "server": server_name, "status": "stopped"}


@router.get("/tools")
async def list_all_mcp_tools(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """List all currently active tools provided by MCP servers."""
    service = get_mcp_service()
    all_tools = []
    for s_name, client in service.clients.items():
        for t in client.tools:
            all_tools.append({
                "server": s_name,
                "tool_name": t.get("name"),
                "skill_name": f"mcp__{s_name}__{t.get('name')}",
                "description": t.get("description"),
                "schema": t.get("inputSchema"),
            })
    return {"tools": all_tools, "total": len(all_tools)}
