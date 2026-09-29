import json
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError
from backend.app.db.models import Approval, User
from backend.app.db.session import get_db
from backend.app.dependencies import get_current_owner
from backend.app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Approvals & Human-in-the-Loop"])


class ApprovalResponse(BaseModel):
    id: str
    tool_call_id: str
    skill_name: str | None = None
    arguments: dict[str, Any] | None = None
    args_hash: str
    status: str
    expires_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    created_at: datetime

    @classmethod
    def from_orm_model(cls, approval: Approval) -> "ApprovalResponse":
        skill_name: str | None = None
        arguments: dict[str, Any] | None = None
        if approval.tool_call:
            skill_name = approval.tool_call.skill_name
            try:
                arguments = json.loads(approval.tool_call.arguments_json)
            except Exception:
                arguments = {}
        return cls(
            id=approval.id,
            tool_call_id=approval.tool_call_id,
            skill_name=skill_name,
            arguments=arguments,
            args_hash=approval.args_hash,
            status=approval.status,
            expires_at=approval.expires_at,
            decided_at=approval.decided_at,
            decided_by=approval.decided_by,
            created_at=approval.created_at,
        )


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "deny"]
    arguments: dict[str, Any] | None = Field(
        default=None,
        description="Optional current arguments to cryptographically verify against original args_hash",
    )


@router.get("/pending", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    _: Annotated[User, Depends(get_current_owner)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalResponse]:
    """List all pending tool approvals that have not yet expired."""
    service = ApprovalService(db)
    approvals = await service.list_pending(limit=limit)
    return [ApprovalResponse.from_orm_model(a) for a in approvals]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval_details(
    approval_id: str,
    _: Annotated[User, Depends(get_current_owner)],
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """Retrieve details for a specific approval request."""
    service = ApprovalService(db)
    approval = await service.get_approval(approval_id)
    if not approval:
        raise NotFoundError(f"Approval request '{approval_id}' was not found.")
    return ApprovalResponse.from_orm_model(approval)


@router.post("/{approval_id}/respond", response_model=ApprovalResponse)
async def respond_to_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    current_user: Annotated[User, Depends(get_current_owner)],
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """
    Approve or deny a pending tool call.
    Validates single-use transition, unexpired TTL, and cryptographic arguments hash integrity.
    """
    service = ApprovalService(db)
    resolved = await service.respond(
        approval_id=approval_id,
        decision=body.decision,
        user_id=current_user.id,
        current_arguments=body.arguments,
    )
    return ApprovalResponse.from_orm_model(resolved)
