import json
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Conversation, Message, ToolCall


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_conversation(
        self, user_id: str, title: str = "New Conversation"
    ) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def get_conversation(
        self, conversation_id: str, user_id: str | None = None
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        if user_id:
            stmt = stmt.where(Conversation.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_conversation(
        self, conversation_id: str, user_id: str | None = None
    ) -> bool:
        stmt = delete(Conversation).where(Conversation.id == conversation_id)
        if user_id:
            stmt = stmt.where(Conversation.user_id == user_id)
        result = await self.db.execute(stmt)
        await self.db.flush()
        rowcount = int(getattr(result, "rowcount", 0) or 0)
        return rowcount > 0

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model_used: str | None = None,
        token_count: int = 0,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_used=model_used,
            token_count=token_count,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_messages(
        self, conversation_id: str, limit: int = 100
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.tool_calls))
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_tool_call(
        self,
        message_id: str | None,
        skill_name: str,
        arguments: dict[str, Any],
        status: str = "pending",
    ) -> ToolCall:
        tool_call = ToolCall(
            message_id=message_id,
            skill_name=skill_name,
            arguments_json=json.dumps(arguments),
            status=status,
        )
        self.db.add(tool_call)
        await self.db.flush()
        return tool_call

    async def update_tool_call(
        self,
        tool_call_id: str,
        status: str,
        result_json: str | None = None,
        execution_time_ms: float | None = None,
    ) -> ToolCall | None:
        stmt = select(ToolCall).where(ToolCall.id == tool_call_id)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            record.status = status
            if result_json is not None:
                record.result_json = result_json
            if execution_time_ms is not None:
                record.execution_time_ms = execution_time_ms
            await self.db.flush()
        return record
