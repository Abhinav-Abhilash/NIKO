import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.security import hash_password
from backend.app.db.models import User
from backend.app.services.task_scheduler_service import TaskSchedulerService
from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.schedule_task_skill import ScheduleTaskSkill


@pytest.mark.asyncio
async def test_schedule_task_skill_manifest() -> None:
    skill = ScheduleTaskSkill()
    assert skill.manifest.name == "schedule_task"
    assert skill.manifest.default_tier == "CONFIRM"
    assert skill.manifest.default_autonomy == "ask"


@pytest.mark.asyncio
async def test_schedule_task_skill_requires_action() -> None:
    skill = ScheduleTaskSkill()
    ctx = SkillContext(request_id="req_sched_empty", user_id="user_1", provenance="direct")
    with pytest.raises(ValidationFailedError, match="Parameter 'action' is required"):
        await skill.execute({}, ctx)


@pytest.mark.asyncio
async def test_schedule_task_skill_lifecycle(db_session: AsyncSession) -> None:
    user = User(username="skill_sched_user", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    service = TaskSchedulerService(db_session=db_session)
    skill = ScheduleTaskSkill(scheduler_service=service)
    ctx = SkillContext(request_id="req_sched_test", user_id=user.id, provenance="direct")

    # 1. Create interval task
    create_res = await skill.execute(
        {
            "action": "create",
            "name": "Check Health",
            "schedule_type": "interval",
            "interval_seconds": 600,
            "action_name": "system_stats",
            "payload": {"detail": True},
        },
        ctx,
    )
    assert create_res.success is True
    task_id = create_res.data["id"]
    assert task_id is not None
    assert create_res.data["name"] == "Check Health"
    assert create_res.data["status"] == "active"

    # 2. List tasks
    list_res = await skill.execute({"action": "list"}, ctx)
    assert list_res.success is True
    assert list_res.data["count"] == 1
    assert list_res.data["tasks"][0]["id"] == task_id

    # 3. Get task
    get_res = await skill.execute({"action": "get", "task_id": task_id}, ctx)
    assert get_res.success is True
    assert get_res.data["id"] == task_id
    assert get_res.data["name"] == "Check Health"

    # 4. Pause task
    pause_res = await skill.execute({"action": "pause", "task_id": task_id}, ctx)
    assert pause_res.success is True
    assert pause_res.data["status"] == "paused"

    # 5. Resume task
    resume_res = await skill.execute({"action": "resume", "task_id": task_id}, ctx)
    assert resume_res.success is True
    assert resume_res.data["status"] == "active"

    # 6. Delete task
    del_res = await skill.execute({"action": "delete", "task_id": task_id}, ctx)
    assert del_res.success is True
    assert del_res.data["id"] == task_id

    # Verify deleted
    with pytest.raises(ValidationFailedError):
        await skill.execute({"action": "get", "task_id": ""}, ctx)
