import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_audit_service_recording_and_querying(db_session: AsyncSession) -> None:
    service = AuditService(db_session)

    # 1. Record two command actions
    log1 = await service.record_command(
        request_id="req_001",
        skill_name="system_stats",
        permission_tier="SAFE",
        provenance="direct",
        arguments={"detail": True},
        status="success",
    )
    assert log1.id is not None
    assert log1.request_id == "req_001"

    log2 = await service.record_command(
        request_id="req_002",
        skill_name="open_app",
        permission_tier="CONFIRM",
        provenance="external_untrusted",
        arguments={"target": "notepad.exe"},
        status="blocked",
    )
    assert log2.status == "blocked"

    await db_session.commit()

    # 2. Query audit trail with filters
    all_logs = await service.get_audit_trail()
    assert len(all_logs) >= 2

    filtered_logs = await service.get_audit_trail(skill_name="open_app")
    assert len(filtered_logs) == 1
    assert filtered_logs[0].skill_name == "open_app"
    assert filtered_logs[0].permission_tier == "CONFIRM"
    assert filtered_logs[0].provenance == "external_untrusted"
