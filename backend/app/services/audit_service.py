import json
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.db.models import CommandLog
from backend.app.repositories.audit_repository import AuditRepository

logger = get_logger("audit_service")


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditRepository(db)

    async def record_command(
        self,
        request_id: str,
        skill_name: str,
        permission_tier: str,
        provenance: str,
        arguments: dict[str, Any] | str,
        status: str,
        user_id: str | None = None,
        approval_id: str | None = None,
        client_ip: str | None = None,
    ) -> CommandLog:
        """Write an action execution record to command_logs."""
        args_str = arguments if isinstance(arguments, str) else json.dumps(arguments, sort_keys=True)

        log = await self.repo.create_log(
            request_id=request_id,
            user_id=user_id,
            approval_id=approval_id,
            skill_name=skill_name,
            permission_tier=permission_tier,
            provenance=provenance,
            arguments_json=args_str,
            status=status,
            client_ip=client_ip,
        )
        logger.info(
            "Command execution logged",
            request_id=request_id,
            skill_name=skill_name,
            permission_tier=permission_tier,
            status=status,
        )
        return log

    async def get_audit_trail(
        self,
        skill_name: str | None = None,
        permission_tier: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CommandLog]:
        return await self.repo.list_logs(
            skill_name=skill_name,
            permission_tier=permission_tier,
            status=status,
            limit=limit,
            offset=offset,
        )
