from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.exceptions import ValidationFailedError
from backend.app.db.session import get_session_maker
from backend.app.services.memory_service import MemoryService
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult


class RememberSkill(BaseSkill):
    """Stores facts, user preferences, relationships, and details in long-term memory."""

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.session_factory = session_factory or get_session_maker()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="remember",
            description="Store a new fact, preference, contact, or detail in persistent memory.",
            default_tier="SAFE",
            default_autonomy="auto+log",
            timeout_seconds=10,
            parameters_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The exact fact or preference to remember.",
                    },
                    "key": {
                        "type": "string",
                        "description": "Optional unique slug or key for the memory (e.g. 'sister_birthday', 'coffee_order').",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category for the memory (e.g. 'personal', 'preference', 'work', 'general').",
                        "default": "general",
                    },
                    "pinned": {
                        "type": "boolean",
                        "description": "Whether this memory is a core fact that should be pinned to the system prompt.",
                        "default": False,
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        content = (arguments.get("content") or "").strip()
        if not content:
            raise ValidationFailedError("Parameter 'content' cannot be empty.")

        key = arguments.get("key")
        category = arguments.get("category") or "general"
        pinned = bool(arguments.get("pinned", False))
        user_id = context.user_id or "default_user"

        if self.memory_service:
            res = await self.memory_service.remember(
                user_id=user_id,
                content=content,
                key=key,
                category=category,
                pinned=pinned,
                provenance=context.provenance,
            )
        else:
            async with self.session_factory() as session:
                service = MemoryService(session)
                res = await service.remember(
                    user_id=user_id,
                    content=content,
                    key=key,
                    category=category,
                    pinned=pinned,
                    provenance=context.provenance,
                )
                await session.commit()

        return SkillResult(success=True, data=res)


class RecallSkill(BaseSkill):
    """Retrieves relevant facts and preferences from long-term memory."""

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.session_factory = session_factory or get_session_maker()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="recall",
            description="Search long-term memory for relevant facts, preferences, or details.",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search phrase or keywords to find memories for.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to return (default: 5).",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter.",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        query = (arguments.get("query") or "").strip()
        if not query:
            raise ValidationFailedError("Parameter 'query' cannot be empty.")

        limit = int(arguments.get("limit") or 5)
        category = arguments.get("category")
        user_id = context.user_id or "default_user"

        if self.memory_service:
            memories = await self.memory_service.recall(
                user_id=user_id,
                query=query,
                limit=limit,
                category=category,
            )
        else:
            async with self.session_factory() as session:
                service = MemoryService(session)
                memories = await service.recall(
                    user_id=user_id,
                    query=query,
                    limit=limit,
                    category=category,
                )
                await session.commit()

        data = {
            "count": len(memories),
            "memories": [
                {
                    "id": m.id,
                    "key": m.key,
                    "content": m.content,
                    "category": m.category,
                    "pinned": m.pinned,
                }
                for m in memories
            ],
        }
        return SkillResult(success=True, data=data)


class ForgetSkill(BaseSkill):
    """Removes a specific memory or preference from long-term memory."""

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.session_factory = session_factory or get_session_maker()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="forget",
            description="Delete a fact or preference from persistent memory by key or ID.",
            default_tier="CONFIRM",
            default_autonomy="ask",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Unique key/slug of the memory to forget.",
                    },
                    "memory_id": {
                        "type": "string",
                        "description": "Unique ID of the memory to forget.",
                    },
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        key = arguments.get("key")
        memory_id = arguments.get("memory_id")
        if not key and not memory_id:
            raise ValidationFailedError("At least one of 'key' or 'memory_id' must be specified.")

        user_id = context.user_id or "default_user"

        if self.memory_service:
            deleted = await self.memory_service.forget(user_id=user_id, memory_id=memory_id, key=key)
        else:
            async with self.session_factory() as session:
                service = MemoryService(session)
                deleted = await service.forget(user_id=user_id, memory_id=memory_id, key=key)
                await session.commit()

        return SkillResult(
            success=True,
            data={
                "deleted": deleted,
                "key": key,
                "memory_id": memory_id,
            },
        )


class ListMemoriesSkill(BaseSkill):
    """Lists stored memories, optionally filtered by category."""

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.session_factory = session_factory or get_session_maker()

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="list_memories",
            description="List memories stored in long-term memory.",
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=5,
            parameters_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category filter.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to return (default: 20).",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        category = arguments.get("category")
        limit = int(arguments.get("limit") or 20)
        user_id = context.user_id or "default_user"

        if self.memory_service:
            memories = await self.memory_service.list_memories(
                user_id=user_id,
                category=category,
                limit=limit,
            )
        else:
            async with self.session_factory() as session:
                service = MemoryService(session)
                memories = await service.list_memories(
                    user_id=user_id,
                    category=category,
                    limit=limit,
                )

        return SkillResult(
            success=True,
            data={
                "count": len(memories),
                "memories": [
                    {
                        "id": m.id,
                        "key": m.key,
                        "content": m.content,
                        "category": m.category,
                        "pinned": m.pinned,
                        "source": m.source,
                    }
                    for m in memories
                ],
            },
        )
