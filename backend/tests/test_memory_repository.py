import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import hash_password
from backend.app.db.models import User
from backend.app.repositories.memory_repository import SQLiteMemoryRepository


@pytest.mark.asyncio
async def test_memory_repository_fts_sync_and_paraphrase_recall(db_session: AsyncSession) -> None:
    # 1. Create test user
    user = User(username="mem_user_1", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    repo = SQLiteMemoryRepository(db_session)

    # 2. Store memory with light-model enriched keywords
    memory = await repo.create_memory(
        user_id=user.id,
        content="My sister Sarah's birthday is on June 5th",
        keywords="sibling bday family june celebration",
        key="sarah_bday",
        category="family",
    )
    assert memory.id is not None

    # 3. Test paraphrase recall with keywords: 'sibling bday' (words not in content, only in keywords)
    results = await repo.search_memories(user_id=user.id, query="sibling bday")
    assert len(results) == 1
    assert results[0].id == memory.id
    assert "Sarah" in results[0].content

    # 4. Test missing word / relaxed matching: 'sarah' (matches content even though 'birthday' omitted)
    results_single = await repo.search_memories(user_id=user.id, query="sarah")
    assert len(results_single) == 1
    assert results_single[0].id == memory.id

    # 5. Test FTS update trigger sync
    updated = await repo.update_memory(
        memory_id=memory.id,
        user_id=user.id,
        content="My sister Sarah's wedding anniversary is August 10th",
        keywords="sibling anniversary marriage august",
        key="sarah_anniversary",
    )
    assert updated is not None

    # Search for new keyword 'marriage'
    res_updated = await repo.search_memories(user_id=user.id, query="marriage")
    assert len(res_updated) == 1
    assert "wedding anniversary" in res_updated[0].content

    # Old keyword 'bday' should no longer match
    res_old = await repo.search_memories(user_id=user.id, query="bday")
    assert len(res_old) == 0

    # 6. Test FTS delete trigger sync
    deleted = await repo.delete_memory(memory_id=memory.id, user_id=user.id)
    assert deleted is True

    res_deleted = await repo.search_memories(user_id=user.id, query="marriage")
    assert len(res_deleted) == 0


@pytest.mark.asyncio
async def test_memory_repository_deduplication(db_session: AsyncSession) -> None:
    user = User(username="mem_user_dedupe", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    repo = SQLiteMemoryRepository(db_session)

    # First insert
    m1 = await repo.create_memory(
        user_id=user.id,
        content="I prefer dark mode in all applications",
        keywords="ui theme darkmode",
        category="preferences",
    )

    # Duplicate insert with different case/spaces and extra keywords
    m2 = await repo.create_memory(
        user_id=user.id,
        content="  i prefer dark mode in all applications  ",
        keywords="appearance style",
        category="preferences",
    )

    # Should update existing record instead of creating a second row
    assert m1.id == m2.id
    count = await repo.count_memories(user.id)
    assert count == 1
    assert "appearance" in m2.keywords
    assert "darkmode" in m2.keywords


@pytest.mark.asyncio
async def test_memory_repository_cap_enforcement(db_session: AsyncSession) -> None:
    user = User(username="mem_user_cap", password_hash=hash_password("pw123"), role="owner")
    db_session.add(user)
    await db_session.flush()

    # Create repo with tiny cap of 3 memories
    repo = SQLiteMemoryRepository(db_session, max_memory_cap=3)

    # Pinned memory (should never be evicted)
    pinned_mem = await repo.create_memory(
        user_id=user.id,
        content="Core User Profile: Lead Engineer",
        pinned=True,
    )

    # 2 unpinned memories
    await repo.create_memory(user_id=user.id, content="Note 1")
    await repo.create_memory(user_id=user.id, content="Note 2")

    count = await repo.count_memories(user.id)
    assert count == 3

    # Add 4th memory -> should trigger eviction of oldest unpinned ('Note 1')
    await repo.create_memory(user_id=user.id, content="Note 3")

    count_after = await repo.count_memories(user.id)
    assert count_after == 3

    # Pinned memory must still exist
    all_memories = await repo.list_memories(user.id)
    all_contents = [m.content for m in all_memories]
    assert pinned_mem.content in all_contents
    assert "Note 3" in all_contents
    assert "Note 1" not in all_contents  # Evicted
