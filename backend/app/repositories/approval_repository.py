from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Approval, ToolCall


class ApprovalRepository:
    """Repository handling database operations for the Approval control model."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_approval(
        self,
        tool_call_id: str,
        args_hash: str,
        expires_at: datetime,
    ) -> Approval:
        approval = Approval(
            tool_call_id=tool_call_id,
            args_hash=args_hash,
            status="pending",
            expires_at=expires_at,
        )
        self.db.add(approval)
        await self.db.flush()
        return approval

    async def get_by_id(self, approval_id: str) -> Approval | None:
        query = (
            select(Approval)
            .options(selectinload(Approval.tool_call))
            .where(Approval.id == approval_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_tool_call_id(self, tool_call_id: str) -> Approval | None:
        query = (
            select(Approval)
            .options(selectinload(Approval.tool_call))
            .where(Approval.tool_call_id == tool_call_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_pending(self, limit: int = 50) -> list[Approval]:
        now = datetime.now(UTC)
        query = (
            select(Approval)
            .options(selectinload(Approval.tool_call).selectinload(ToolCall.message))
            .where(Approval.status == "pending", Approval.expires_at > now)
            .order_by(Approval.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def resolve_approval(
        self,
        approval: Approval,
        status: str,
        decided_by: str,
        decided_at: datetime | None = None,
    ) -> Approval:
        approval.status = status
        approval.decided_by = decided_by
        approval.decided_at = decided_at or datetime.now(UTC)
        await self.db.flush()
        return approval

    async def expire_stale_approvals(self) -> int:
        now = datetime.now(UTC)
        stmt = (
            update(Approval)
            .where(Approval.status == "pending", Approval.expires_at <= now)
            .values(status="expired")
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount) if isinstance(rowcount, int) else 0
