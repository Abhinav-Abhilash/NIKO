from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.services.note_service import NoteService
from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.notes_skill import NotesSkill


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_notes_skill_flow(async_session: AsyncSession) -> None:
    service = NoteService(session=async_session)
    skill = NotesSkill(note_service=service)
    ctx = SkillContext(request_id="test_notes_1", user_id="user_123", provenance="direct")

    # 1. Add note
    add_res = await skill.execute(
        {"action": "add", "title": "Meeting Notes", "content": "Discuss v0.2.0 features", "tags": "work,todo"},
        ctx,
    )
    assert add_res.success is True
    note_id = add_res.data["id"]
    assert add_res.data["title"] == "Meeting Notes"

    # 2. List notes
    list_res = await skill.execute({"action": "list"}, ctx)
    assert list_res.success is True
    assert list_res.data["count"] == 1

    # 3. Search notes
    search_res = await skill.execute({"action": "search", "query": "v0.2.0"}, ctx)
    assert search_res.success is True
    assert search_res.data["count"] == 1

    # 4. Delete note
    del_res = await skill.execute({"action": "delete", "note_id": note_id}, ctx)
    assert del_res.success is True

    # 5. List notes after delete
    list_after = await skill.execute({"action": "list"}, ctx)
    assert list_after.data["count"] == 0
