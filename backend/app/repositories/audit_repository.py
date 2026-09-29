from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import CommandLog


class AuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_log(
        self,
        request_id: str,
        skill_name: str,
        permission_tier: str,
        provenance: str,
        arguments_json: str,
        status: str,
        user_id: str | None = None,
        approval_id: str | None = None,
        client_ip: str | None = None,
    ) -> CommandLog:
        log = CommandLog(
            request_id=request_id,
            user_id=user_id,
            approval_id=approval_id,
            skill_name=skill_name,
            permission_tier=permission_tier,
            provenance=provenance,
            arguments_json=arguments_json,
            status=status,
            client_ip=client_ip,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_logs(
        self,
        skill_name: str | None = None,
        permission_tier: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CommandLog]:
        query = select(CommandLog).options(selectinload(CommandLog.approval))

        if skill_name:
            query = query.where(CommandLog.skill_name == skill_name)
        if permission_tier:
            query = query.where(CommandLog.permission_tier == permission_tier)
        if status:
            query = query.where(CommandLog.status == status)
        if start_date:
            query = query.where(CommandLog.created_at >= start_date)
        if end_date:
            query = query.where(CommandLog.created_at <= end_date)

        query = query.order_by(desc(CommandLog.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_logs(
        self,
        skill_name: str | None = None,
        permission_tier: str | None = None,
        status: str | None = None,
    ) -> int:
        query = select(func.count(CommandLog.id))
        if skill_name:
            query = query.where(CommandLog.skill_name == skill_name)
        if permission_tier:
            query = query.where(CommandLog.permission_tier == permission_tier)
        if status:
            query = query.where(CommandLog.status == status)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() or 0
