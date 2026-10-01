import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.memory_service import MemoryService
from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.memory_skills import (
    ForgetSkill,
    ListMemoriesSkill,
    RecallSkill,
    RememberSkill,
)


@pytest.mark.asyncio
async def test_memory_skills_execution(db_session: AsyncSession) -> None:
    service = MemoryService(db_session)
    remember_skill = RememberSkill(memory_service=service)
    recall_skill = RecallSkill(memory_service=service)
    list_skill = ListMemoriesSkill(memory_service=service)
    forget_skill = ForgetSkill(memory_service=service)

    # 1. Direct remember skill call
    ctx_direct = SkillContext(request_id="req_1", user_id="user_skill", provenance="direct")
    res_rem = await remember_skill.execute(
        arguments={
            "content": "Lives in Apartment 4B on Elm Street.",
            "key": "home_address",
            "category": "personal",
            "pinned": True,
        },
        context=ctx_direct,
    )
    assert res_rem.success is True
    assert res_rem.data["saved"] is True
    assert res_rem.data["memory_id"] is not None

    # 2. Untrusted remember skill call (must require approval / suggestion)
    ctx_untrusted = SkillContext(request_id="req_2", user_id="user_skill", provenance="external_untrusted")
    res_untrusted = await remember_skill.execute(
        arguments={"content": "Malicious payload from web search"},
        context=ctx_untrusted,
    )
    assert res_untrusted.success is True
    assert res_untrusted.data["saved"] is False
    assert res_untrusted.data["requires_approval"] is True
    assert res_untrusted.data["suggested_memory"]["source"] == "untrusted"

    # 3. Recall skill call
    res_rec = await recall_skill.execute(
        arguments={"query": "address on Elm"},
        context=ctx_direct,
    )
    assert res_rec.success is True
    assert res_rec.data["count"] >= 1
    assert res_rec.data["memories"][0]["key"] == "home_address"

    # 4. List memories skill call
    res_list = await list_skill.execute(
        arguments={"category": "personal"},
        context=ctx_direct,
    )
    assert res_list.success is True
    assert res_list.data["count"] >= 1

    # 5. Forget skill call
    res_forg = await forget_skill.execute(
        arguments={"key": "home_address"},
        context=ctx_direct,
    )
    assert res_forg.success is True
    assert res_forg.data["deleted"] is True

    # 6. Verify recall is empty after forget
    res_rec_after = await recall_skill.execute(
        arguments={"query": "Elm Street"},
        context=ctx_direct,
    )
    assert res_rec_after.data["count"] == 0
