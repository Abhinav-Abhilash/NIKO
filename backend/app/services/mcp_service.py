import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult, SkillTier
from backend.app.skills.registry import SkillRegistry, get_skill_registry

logger = get_logger("mcp_service")

CONFIG_PATH = Path("storage/mcp_servers.json")


class MCPServerConfig(BaseModel):
    name: str = Field(..., description="Unique server identifier")
    command: str = Field(..., description="Executable command, e.g. 'npx' or 'python'")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    tier: SkillTier = Field(default="CONFIRM", description="Security tier for tools from this server")
    autonomy: str = Field(default="ask", description="Default autonomy: 'ask', 'auto', or 'auto+log'")
    enabled: bool = Field(default=True, description="Whether server is active")
    timeout_seconds: int = Field(default=15, description="Tool execution timeout sandbox limit")


class MCPJsonRpcClient:
    """
    Asynchronous JSON-RPC 2.0 stdio client for Model Context Protocol (MCP) servers.
    Provides sub-process execution, protocol negotiation, tool enumeration, and sandboxed calls.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self.tools: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Start the MCP server subprocess and perform protocol handshake."""
        async with self._lock:
            if self.process and self.process.returncode is None:
                return

            try:
                # Merge environment variables
                import os
                merged_env = os.environ.copy()
                merged_env.update(self.config.env)

                self.process = await asyncio.create_subprocess_exec(
                    self.config.command,
                    *self.config.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=merged_env,
                )
                self._reader_task = asyncio.create_task(self._read_stdout_loop())

                # Step 1: Protocol handshake
                init_res = await self._send_request(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": "niko-mcp-client", "version": "0.3.0"},
                    },
                    timeout=10.0,
                )
                logger.info("MCP server initialized", server=self.config.name, result=init_res)

                # Step 2: Notify initialized
                await self._send_notification("notifications/initialized", {})

                # Step 3: Fetch available tools
                tools_res = await self._send_request("tools/list", {}, timeout=10.0)
                self.tools = tools_res.get("tools", [])
                logger.info(
                    "MCP server tools enumerated",
                    server=self.config.name,
                    tool_count=len(self.tools),
                )
            except Exception as exc:
                logger.error("Failed to start MCP server", server=self.config.name, error=str(exc))
                await self.stop()
                raise

    async def _read_stdout_loop(self) -> None:
        """Continuously read JSON-RPC messages from server stdout."""
        if not self.process or not self.process.stdout:
            return

        try:
            while not self.process.stdout.at_eof():
                line = await self.process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str:
                    continue

                try:
                    msg = json.loads(line_str)
                    if "id" in msg:
                        req_id = msg["id"]
                        future = self._pending_requests.pop(req_id, None)
                        if future and not future.done():
                            if "error" in msg:
                                future.set_exception(
                                    RuntimeError(f"MCP RPC Error: {msg['error']}")
                                )
                            else:
                                future.set_result(msg.get("result", {}))
                except json.JSONDecodeError:
                    continue
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("MCP reader error", server=self.config.name, error=str(exc))

    async def _send_request(self, method: str, params: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
        """Send a JSON-RPC request and await response with timeout."""
        if not self.process or self.process.returncode is not None or not self.process.stdin:
            raise RuntimeError(f"MCP server '{self.config.name}' is not running.")

        self._request_id += 1
        req_id = self._request_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_requests[req_id] = future

        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        raw = json.dumps(msg) + "\n"
        self.process.stdin.write(raw.encode("utf-8"))
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError(f"MCP request '{method}' to '{self.config.name}' timed out after {timeout}s.")

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a fire-and-forget JSON-RPC notification."""
        if not self.process or not self.process.stdin:
            return
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        raw = json.dumps(msg) + "\n"
        self.process.stdin.write(raw.encode("utf-8"))
        await self.process.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a tool on the MCP server under timeout sandbox."""
        res = await self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            timeout=float(self.config.timeout_seconds),
        )
        return res.get("content") or res

    async def stop(self) -> None:
        """Terminate the MCP server subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None

        for fut in self._pending_requests.values():
            if not fut.done():
                fut.cancel()
        self._pending_requests.clear()

        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


class MCPDynamicSkill(BaseSkill):
    """Dynamically generated BaseSkill wrapper for an MCP server tool."""

    def __init__(
        self,
        server_config: MCPServerConfig,
        tool_def: dict[str, Any],
        client: MCPJsonRpcClient,
    ) -> None:
        self.server_config = server_config
        self.tool_def = tool_def
        self.client = client
        self.tool_raw_name = tool_def.get("name", "unnamed")
        self.skill_name = f"mcp__{server_config.name}__{self.tool_raw_name}"

    @property
    def manifest(self) -> SkillManifest:
        raw_schema = self.tool_def.get("inputSchema", {})
        # Ensure parameters_schema adheres to OpenAI-compatible JSON Schema
        if not isinstance(raw_schema, dict) or "type" not in raw_schema:
            raw_schema = {
                "type": "object",
                "properties": raw_schema.get("properties", {}),
                "required": raw_schema.get("required", []),
            }

        return SkillManifest(
            name=self.skill_name,
            description=f"[MCP: {self.server_config.name}] {self.tool_def.get('description', '')}",
            default_tier=self.server_config.tier,
            default_autonomy=self.server_config.autonomy,  # type: ignore[arg-type]
            timeout_seconds=self.server_config.timeout_seconds,
            parameters_schema=raw_schema,
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        try:
            result = await self.client.call_tool(self.tool_raw_name, arguments)
            return SkillResult(success=True, data=result)
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))


class MCPService:
    """
    Central service for managing external MCP servers, tool discovery,
    and automatic skill registration.
    """

    def __init__(self, registry: SkillRegistry | None = None, config_path: Path = CONFIG_PATH) -> None:
        self.registry = registry or get_skill_registry()
        self.config_path = config_path
        self.clients: dict[str, MCPJsonRpcClient] = {}
        self.registered_skills: dict[str, list[str]] = {}

    def load_configs(self) -> dict[str, MCPServerConfig]:
        """Load configured MCP servers from disk."""
        if not self.config_path.exists():
            return {}

        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            servers_raw = data.get("mcpServers", {})
            configs = {}
            for name, cfg in servers_raw.items():
                configs[name] = MCPServerConfig(name=name, **cfg)
            return configs
        except Exception as exc:
            logger.warning("Failed to parse MCP servers configuration", error=str(exc))
            return {}

    def save_configs(self, configs: dict[str, MCPServerConfig]) -> None:
        """Save MCP servers configuration to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "mcpServers": {
                name: cfg.model_dump(exclude={"name"}) for name, cfg in configs.items()
            }
        }
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def start_server(self, config: MCPServerConfig) -> list[str]:
        """Start an MCP server, enumerate tools, and register them into SkillRegistry."""
        if config.name in self.clients:
            await self.stop_server(config.name)

        client = MCPJsonRpcClient(config)
        await client.start()
        self.clients[config.name] = client

        registered_names: list[str] = []
        for tool_def in client.tools:
            skill = MCPDynamicSkill(config, tool_def, client)
            self.registry.register(skill)
            registered_names.append(skill.manifest.name)

        self.registered_skills[config.name] = registered_names
        logger.info(
            "Registered MCP tools into SkillRegistry",
            server=config.name,
            skills=registered_names,
        )
        return registered_names

    async def stop_server(self, server_name: str) -> None:
        """Stop an MCP server and unregister its dynamic skills."""
        skill_names = self.registered_skills.pop(server_name, [])
        for name in skill_names:
            if self.registry.has(name):
                self.registry._skills.pop(name, None)

        client = self.clients.pop(server_name, None)
        if client:
            await client.stop()
        logger.info("Stopped MCP server and cleaned up skills", server=server_name)

    async def initialize_all_servers(self) -> None:
        """Initialize all enabled MCP servers at startup."""
        configs = self.load_configs()
        for name, config in configs.items():
            if config.enabled:
                try:
                    await self.start_server(config)
                except Exception as exc:
                    logger.warning("Failed to auto-start MCP server on boot", server=name, error=str(exc))

    async def shutdown(self) -> None:
        """Cleanly stop all active MCP servers."""
        for name in list(self.clients.keys()):
            await self.stop_server(name)


_global_mcp_service: MCPService | None = None


def get_mcp_service() -> MCPService:
    global _global_mcp_service
    if _global_mcp_service is None:
        _global_mcp_service = MCPService()
    return _global_mcp_service
