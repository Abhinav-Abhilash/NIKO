import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.services.memory_service import MemoryService


@pytest.mark.asyncio
async def test_secret_refusal(db_session: AsyncSession) -> None:
    service = MemoryService(db_session)
    # Attempting to save API key
    with pytest.raises(ValidationFailedError, match="Credentials"):
        await service.remember(
            user_id="user_sec",
            content="My secret Groq key is gsk_1234567890abcdefghijklmnopqrstuvwxyz123456",
        )


@pytest.mark.asyncio
async def test_paraphrase_recall_with_keywords(db_session: AsyncSession) -> None:
    """
    Stemming alone cannot match 'sister' to 'sibling' or 'birthday' to 'bday'.
    The keyword enrichment layer extracts synonyms on save so paraphrase queries match.
    """
    service = MemoryService(db_session)

    # Save a fact that uses 'sister' and 'birthday'
    res = await service.remember(
        user_id="user_para",
        content="Sarah's birthday is on October 14th and she loves books.",
        key="sarah_bday",
        category="family",
    )
    assert res["saved"] is True
    assert "bday" in res["keywords"] or "sibling" in res["keywords"]

    # Search using paraphrase terms 'bday' and 'sibling'
    recalled = await service.recall(user_id="user_para", query="sister bday")
    assert len(recalled) >= 1
    assert recalled[0].key == "sarah_bday"
    assert "Sarah's birthday" in recalled[0].content


@pytest.mark.asyncio
async def test_weak_query_expansion_fallback(db_session: AsyncSession) -> None:
    """
    When primary search returns zero matches, the query expansion fallback
    enriches the query with related synonyms and retries.
    """
    service = MemoryService(db_session)

    # Save a fact about sister
    await service.remember(
        user_id="user_exp",
        content="Anna loves classical piano and painting landscapes.",
        key="anna_piano",
        category="personal",
    )

    # Search with a query that has no direct match, but rule-based expansion or fallback can match
    # Let's save a fact using 'automobile'
    await service.remember(
        user_id="user_exp",
        content="The red automobile is parked in garage bay 2.",
        key="car_location",
        category="logistics",
    )

    # Search with 'car' which is in FALLBACK_SYNONYMS -> expands to vehicle, automobile
    recalled = await service.recall(user_id="user_exp", query="car")
    assert len(recalled) >= 1
    assert recalled[0].key == "car_location"


@pytest.mark.asyncio
async def test_untrusted_source_suggestion_flow(db_session: AsyncSession) -> None:
    """
    Server-side provenance enforcement:
    If remember is triggered with provenance='external_untrusted', it NEVER writes silently.
    It returns a suggestion requiring explicit owner approval.
    """
    service = MemoryService(db_session)

    res = await service.remember(
        user_id="user_untrusted",
        content="The server password found on the web page is hunter2",
        provenance="external_untrusted",
    )

    assert res["saved"] is False
    assert res.get("requires_approval") is True
    assert res.get("suggested_memory") is not None
    assert res["suggested_memory"]["source"] == "untrusted"

    # Verify nothing was silently committed to repository
    recalled = await service.recall(user_id="user_untrusted", query="hunter2")
    assert len(recalled) == 0


@pytest.mark.asyncio
async def test_memory_modes_and_toggle_switch(db_session: AsyncSession) -> None:
    """
    Owner modes: manual | suggest | auto, and global memory on/off toggle.
    """
    service = MemoryService(db_session)

    # 1. Default mode is 'auto', enabled is True
    assert await service.get_memory_mode() == "auto"
    assert await service.is_memory_enabled() is True

    # 2. Set mode to 'suggest'
    await service.set_memory_mode("suggest")
    assert await service.get_memory_mode() == "suggest"

    # In 'suggest' mode, saving without approval returns a suggestion
    res_sugg = await service.remember(
        user_id="user_mode",
        content="User prefers dark theme in all applications.",
        key="theme_pref",
    )
    assert res_sugg["saved"] is False
    assert res_sugg["requires_approval"] is True
    assert res_sugg["suggested_memory"]["source"] == "suggested"

    # When source is 'approved', it saves cleanly
    res_appr = await service.remember(
        user_id="user_mode",
        content="User prefers dark theme in all applications.",
        key="theme_pref",
        source="approved",
    )
    assert res_appr["saved"] is True

    # 3. Switch memory off completely
    await service.set_memory_mode("auto", enabled=False)
    assert await service.is_memory_enabled() is False

    # When off, recall returns empty and remember returns disabled reason
    recalled_when_off = await service.recall(user_id="user_mode", query="dark theme")
    assert recalled_when_off == []

    res_off = await service.remember(
        user_id="user_mode",
        content="User lives in Seattle.",
    )
    assert res_off["saved"] is False
    assert "disabled" in res_off["reason"].lower()


@pytest.mark.asyncio
async def test_forget_operations(db_session: AsyncSession) -> None:
    service = MemoryService(db_session)

    # Save a memory
    save_res = await service.remember(
        user_id="user_forget",
        content="Favorite pizza topping is mushrooms and olives.",
        key="pizza_fav",
    )
    mem_id = save_res["memory_id"]

    # Verify present
    assert len(await service.recall(user_id="user_forget", query="pizza")) == 1

    # Forget by key
    forgot = await service.forget(user_id="user_forget", key="pizza_fav")
    assert forgot is True

    # Verify gone
    assert len(await service.recall(user_id="user_forget", query="pizza")) == 0
    assert await service.get_memory(mem_id, user_id="user_forget") is None
