import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.events import EventBus, get_event_bus
from backend.app.core.exceptions import NotFoundError, ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.core.security import compute_args_hash, validate_approval_state
from backend.app.db.models import Approval
from backend.app.repositories.approval_repository import ApprovalRepository

logger = get_logger("approval_service")


class ApprovalService:
    """
    Manages cryptographic human-in-the-loop approvals for sensitive tool calls.
    Enforces 30-second expiry, args_hash verification, and atomic state transitions.
    """

    def __init__(
        self,
        db: AsyncSession,
        event_bus: EventBus | None = None,
    ) -> None:
        self.db = db
        self.repo = ApprovalRepository(db)
        self.event_bus = event_bus or get_event_bus()

    async def create_approval(
        self,
        tool_call_id: str,
        arguments: dict[str, Any],
        skill_name: str = "",
        expires_in_seconds: int = 30,
    ) -> Approval:
        """Create a cryptographic approval request with a default 30-second TTL."""
        args_hash = compute_args_hash(arguments)
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)

        approval = await self.repo.create_approval(
            tool_call_id=tool_call_id,
            args_hash=args_hash,
            expires_at=expires_at,
        )

        logger.info(
            "Approval request created",
            approval_id=approval.id,
            tool_call_id=tool_call_id,
            skill_name=skill_name,
            expires_at=expires_at.isoformat(),
        )

        await self.event_bus.publish(
            topic="approval",
            event_type="request",
            payload={
                "approval_id": approval.id,
                "tool_call_id": tool_call_id,
                "skill_name": skill_name,
                "arguments": arguments,
                "args_hash": args_hash,
                "expires_at": expires_at.isoformat(),
            },
        )

        await self.event_bus.publish(
            topic="chat",
            event_type="tool_call",
            payload={
                "tool_call_id": tool_call_id,
                "skill_name": skill_name,
                "arguments": arguments,
                "status": "awaiting_approval",
                "approval_id": approval.id,
            },
        )

        return approval

    async def respond(
        self,
        approval_id: str,
        decision: str,
        user_id: str,
        current_arguments: dict[str, Any] | None = None,
    ) -> Approval:
        """
        Respond to an approval request ('approve' or 'deny').
        Validates unexpired state, single-use transition, and argument hash integrity.
        """
        decision_clean = decision.strip().lower()
        if decision_clean not in ("approve", "deny"):
            raise ValidationFailedError(
                f"Invalid decision '{decision}'. Must be 'approve' or 'deny'."
            )

        approval = await self.repo.get_by_id(approval_id)
        if not approval:
            raise NotFoundError(f"Approval request '{approval_id}' was not found.")

        # Validate unexpired and pending state
        validate_approval_state(approval.status, approval.expires_at)

        # Cryptographic argument binding check if execution arguments are supplied
        if decision_clean == "approve" and current_arguments is not None:
            computed_hash = compute_args_hash(current_arguments)
            if not hmac.compare_digest(computed_hash, approval.args_hash):
                raise ValidationFailedError(
                    "Cryptographic binding failure: execution arguments differ from user-approved arguments."
                )

        target_status = "approved" if decision_clean == "approve" else "denied"
        resolved = await self.repo.resolve_approval(
            approval=approval,
            status=target_status,
            decided_by=user_id,
        )

        if resolved.tool_call:
            resolved.tool_call.status = "running" if target_status == "approved" else "rejected"

        logger.info(
            "Approval decision recorded",
            approval_id=resolved.id,
            status=resolved.status,
            decided_by=user_id,
        )

        await self.event_bus.publish(
            topic="approval",
            event_type="resolved",
            payload={
                "approval_id": resolved.id,
                "tool_call_id": resolved.tool_call_id,
                "status": resolved.status,
                "decided_by": user_id,
            },
        )

        await self.event_bus.publish(
            topic="chat",
            event_type="tool_call",
            payload={
                "tool_call_id": resolved.tool_call_id,
                "approval_id": resolved.id,
                "status": "running" if target_status == "approved" else "rejected",
                "decision": target_status,
            },
        )

        return resolved

    async def get_approval(self, approval_id: str) -> Approval | None:
        """Retrieve approval details by ID."""
        return await self.repo.get_by_id(approval_id)

    async def list_pending(self, limit: int = 50) -> list[Approval]:
        """List currently pending, unexpired approvals."""
        return await self.repo.list_pending(limit=limit)

    async def expire_stale(self) -> int:
        """Expire all pending approvals that have exceeded their TTL."""
        expired_count = await self.repo.expire_stale_approvals()
        if expired_count > 0:
            logger.info("Expired stale approvals", count=expired_count)
        return expired_count
