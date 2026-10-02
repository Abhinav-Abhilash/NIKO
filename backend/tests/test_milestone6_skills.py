import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.db.models import Reminder, User
from backend.app.services.reminder_service import ReminderService
from backend.app.skills.base import SkillContext
from backend.app.skills.builtin.open_app_skill import OpenAppSkill
from backend.app.skills.builtin.reminders_skill import RemindersSkill
from backend.app.skills.builtin.screenshot_skill import ScreenshotSkill
from backend.app.skills.builtin.volume_brightness_skill import VolumeBrightnessSkill
from backend.app.skills.builtin.web_search_skill import WebSearchSkill
from backend.app.skills.builtin.youtube_play_skill import YouTubePlaySkill


# ---------------------------------------------------------------------------
# 1. OpenAppSkill Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_open_app_skill_manifest() -> None:
    skill = OpenAppSkill()
    assert skill.manifest.name == "open_app"
    assert skill.manifest.default_tier == "CONFIRM"
    assert skill.manifest.default_autonomy == "ask"


@pytest.mark.asyncio
async def test_open_app_skill_requires_app_or_path() -> None:
    skill = OpenAppSkill()
    ctx = SkillContext(request_id="req_open_empty", provenance="direct")
    with pytest.raises(ValidationFailedError, match="Either 'app_name' or 'executable_path'"):
        await skill.execute({}, ctx)


@pytest.mark.asyncio
async def test_open_app_skill_rejects_invalid_arguments_type() -> None:
    skill = OpenAppSkill()
    ctx = SkillContext(request_id="req_open_bad_args", provenance="direct")
    with pytest.raises(ValidationFailedError, match="must be a list of strings"):
        await skill.execute({"app_name": "notepad", "arguments": "not-a-list"}, ctx)


@pytest.mark.asyncio
async def test_open_app_skill_launches_allowlisted_app() -> None:
    skill = OpenAppSkill()
    ctx = SkillContext(request_id="req_open_success", provenance="direct")

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        mock_popen.return_value = mock_proc

        result = await skill.execute({"app_name": "notepad", "arguments": ["test.txt"]}, ctx)

        assert result.success is True
        assert result.data["launched"] is True
        assert result.data["pid"] == 4321
        assert result.data["arguments"] == ["test.txt"]


# ---------------------------------------------------------------------------
# 2. WebSearchSkill Tests & Untrusted Provenance Wrapping
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_web_search_skill_manifest() -> None:
    skill = WebSearchSkill()
    assert skill.manifest.name == "web_search"
    assert skill.manifest.default_tier == "SAFE"
    assert skill.manifest.default_autonomy == "auto"


@pytest.mark.asyncio
async def test_web_search_skill_requires_query() -> None:
    skill = WebSearchSkill()
    ctx = SkillContext(request_id="req_ws_empty", provenance="direct")
    with pytest.raises(ValidationFailedError, match="Search query cannot be empty"):
        await skill.execute({"query": ""}, ctx)


@pytest.mark.asyncio
async def test_web_search_skill_wraps_untrusted_snippets() -> None:
    skill = WebSearchSkill()
    ctx = SkillContext(request_id="req_ws_success", provenance="direct")

    sample_html = """
    <div class="result results_links_deep highlight_d">
        <a class="result__a" href="https://duckduckgo.com/l/?kh=-1&uddg=https%3A%2F%2Fpython.org">Python Programming Language</a>
        <a class="result__snippet">Python is a powerful, dynamic language.</a>
    </div>
    """

    mock_client = AsyncMock()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.text = sample_html
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await skill.execute({"query": "python programming"}, ctx)

        assert result.success is True
        assert result.data["count"] == 1
        res_item = result.data["results"][0]
        assert res_item["title"] == "Python Programming Language"
        assert res_item["url"] == "https://python.org"
        assert "<untrusted_external_content>" in res_item["snippet"]
        assert "</untrusted_external_content>" in res_item["snippet"]
        assert "Python is a powerful" in res_item["snippet"]


# ---------------------------------------------------------------------------
# 3. YouTubePlaySkill Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_youtube_play_skill_manifest() -> None:
    skill = YouTubePlaySkill()
    assert skill.manifest.name == "youtube_play"
    assert skill.manifest.default_tier == "CONFIRM"
    assert skill.manifest.default_autonomy == "auto+log"


@pytest.mark.asyncio
async def test_youtube_play_skill_requires_param() -> None:
    skill = YouTubePlaySkill()
    ctx = SkillContext(request_id="req_yt_empty", provenance="direct")
    with pytest.raises(ValidationFailedError, match="Either 'url' or 'query' must be provided"):
        await skill.execute({}, ctx)


@pytest.mark.asyncio
async def test_youtube_play_skill_formats_search_query() -> None:
    skill = YouTubePlaySkill()
    ctx = SkillContext(request_id="req_yt_query", provenance="direct")

    with patch("webbrowser.open", return_value=True) as mock_open:
        result = await skill.execute({"query": "lofi hip hop radio"}, ctx)
        assert result.success is True
        assert result.data["played"] is True
        assert "https://www.youtube.com/results?search_query=lofi+hip+hop+radio" in result.data["target_url"]
        mock_open.assert_called_once()


@pytest.mark.asyncio
async def test_youtube_play_skill_validates_direct_url() -> None:
    skill = YouTubePlaySkill()
    ctx = SkillContext(request_id="req_yt_url", provenance="direct")

    with patch("webbrowser.open", return_value=True):
        result = await skill.execute({"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}, ctx)
        assert result.success is True
        assert result.data["target_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_youtube_play_skill_rejects_non_youtube_domain() -> None:
    skill = YouTubePlaySkill()
    ctx = SkillContext(request_id="req_yt_bad_host", provenance="direct")

    with pytest.raises(ValidationFailedError, match="not an authorized YouTube domain"):
        await skill.execute({"url": "https://evil-phishing.com/watch?v=fake"}, ctx)


# ---------------------------------------------------------------------------
# 4. ScreenshotSkill Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_screenshot_skill_manifest() -> None:
    skill = ScreenshotSkill()
    assert skill.manifest.name == "screenshot"
    assert skill.manifest.default_tier == "SAFE"
    assert skill.manifest.default_autonomy == "auto"


@pytest.mark.asyncio
async def test_screenshot_skill_execution(tmp_path: Any) -> None:
    skill = ScreenshotSkill()
    ctx = SkillContext(request_id="req_screen", provenance="direct")

    with (
        patch("backend.app.skills.builtin.screenshot_skill.SCREENSHOTS_DIR", tmp_path),
        patch("mss.mss") as mock_mss_cls,
    ):
        mock_sct = MagicMock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 800, "height": 600}, {"left": 0, "top": 0, "width": 800, "height": 600}]
        mock_grab = MagicMock()
        mock_grab.size = (100, 100)
        mock_grab.bgra = b"\x00" * (100 * 100 * 4)
        mock_sct.grab.return_value = mock_grab
        mock_mss_cls.return_value.__enter__.return_value = mock_sct

        result = await skill.execute({"monitor_index": 1, "include_thumbnail_base64": True}, ctx)

        assert result.success is True
        assert result.data["width"] == 100
        assert result.data["height"] == 100
        assert result.data["file_path"] is not None
        assert result.data["thumbnail_base64"] is not None


@pytest.mark.asyncio
async def test_screenshot_skill_hides_and_restores_overlay(tmp_path: Any) -> None:
    """Verify ScreenshotSkill broadcasts overlay:hide before capture and overlay:show after."""
    from backend.app.core.events import get_event_bus
    skill = ScreenshotSkill()
    ctx = SkillContext(request_id="req_screen_overlay", provenance="direct")
    event_bus = get_event_bus()

    published_events = []

    async def subscriber() -> None:
        async for event in event_bus.subscribe("overlay"):
            published_events.append(event)
            if len(published_events) >= 2:
                break

    sub_task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.01)

    with (
        patch("backend.app.skills.builtin.screenshot_skill.SCREENSHOTS_DIR", tmp_path),
        patch("mss.mss") as mock_mss_cls,
    ):
        mock_sct = MagicMock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 800, "height": 600}, {"left": 0, "top": 0, "width": 800, "height": 600}]
        mock_grab = MagicMock()
        mock_grab.size = (50, 50)
        mock_grab.bgra = b"\x00" * (50 * 50 * 4)
        mock_sct.grab.return_value = mock_grab
        mock_mss_cls.return_value.__enter__.return_value = mock_sct

        result = await skill.execute({"monitor_index": 1}, ctx)
        assert result.success is True

    await asyncio.wait_for(sub_task, timeout=2.0)
    assert len(published_events) == 2
    assert published_events[0].event_type == "hide"
    assert published_events[1].event_type == "show"



# ---------------------------------------------------------------------------
# 5. VolumeBrightnessSkill Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_volume_brightness_skill_manifest() -> None:
    skill = VolumeBrightnessSkill()
    assert skill.manifest.name == "volume_brightness"
    assert skill.manifest.default_tier == "CONFIRM"


@pytest.mark.asyncio
async def test_volume_brightness_skill_validation() -> None:
    skill = VolumeBrightnessSkill()
    ctx = SkillContext(request_id="req_vb_val", provenance="direct")

    with pytest.raises(ValidationFailedError, match="Parameter 'action' is required"):
        await skill.execute({}, ctx)

    with pytest.raises(ValidationFailedError, match="requires a valid 'level'"):
        await skill.execute({"action": "set_volume", "level": 150}, ctx)


@pytest.mark.asyncio
async def test_volume_brightness_skill_audio_mock() -> None:
    skill = VolumeBrightnessSkill()
    ctx = SkillContext(request_id="req_vb_audio", provenance="direct")

    with (
        patch("sys.platform", "win32"),
        patch.object(skill, "_handle_audio", return_value={"action": "get_volume", "volume_level": 75, "is_muted": False}),
    ):
        result = await skill.execute({"action": "get_volume"}, ctx)
        assert result.success is True
        assert result.data["volume_level"] == 75


@pytest.mark.asyncio
async def test_volume_brightness_skill_importerror_guards() -> None:
    """Verify missing dependencies return clear skill unavailable errors without crashing."""
    skill = VolumeBrightnessSkill()
    ctx = SkillContext(request_id="req_vb_guard", provenance="direct")

    with patch("sys.platform", "win32"):
        # 1. Test audio missing pycaw/comtypes
        with patch.dict("sys.modules", {"comtypes": None, "pycaw": None, "pycaw.pycaw": None}):
            res_audio = await skill.execute({"action": "get_volume"}, ctx)
            assert res_audio.success is False
            assert "Audio control skill unavailable" in (res_audio.error or "")

        # 2. Test brightness missing screen_brightness_control
        with patch.dict("sys.modules", {"screen_brightness_control": None}):
            res_bright = await skill.execute({"action": "get_brightness"}, ctx)
            assert res_bright.success is False
            assert "Brightness control skill unavailable" in (res_bright.error or "")


# ---------------------------------------------------------------------------
# 6. RemindersSkill & ReminderService Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reminder_service_crud_and_background_firing(db_session: AsyncSession) -> None:
    test_user = User(
        username="reminder_test_owner",
        password_hash="fake_hash",
        role="owner",
    )
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    service = ReminderService(db_session=db_session)

    # 1. Create reminder
    trigger_future = datetime.now(UTC) + timedelta(minutes=10)
    reminder = await service.create_reminder(
        title="Check oven",
        trigger_at=trigger_future,
        description="Bake sourdough bread",
        user_id=test_user.id,
    )
    assert reminder.id is not None
    assert reminder.status == "scheduled"

    # 2. List reminders
    reminders = await service.list_reminders(user_id=test_user.id, status="scheduled")
    assert len(reminders) == 1
    assert reminders[0].title == "Check oven"

    # 3. Cancel reminder
    cancelled = await service.cancel_reminder(reminder_id=reminder.id, user_id=test_user.id)
    assert cancelled.status == "cancelled"

    # 4. Due reminder firing test
    due_reminder = Reminder(
        user_id=test_user.id,
        title="Immediate alarm",
        trigger_at=datetime.now(UTC) - timedelta(seconds=5),
        status="scheduled",
    )
    db_session.add(due_reminder)
    await db_session.commit()

    # Mock session factory for background worker method
    @asynccontextmanager
    async def mock_session_factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    service.session_factory = mock_session_factory

    fired_count = await service.check_and_fire_pending_reminders()
    assert fired_count == 1

    await db_session.refresh(due_reminder)
    assert due_reminder.status == "fired"


@pytest.mark.asyncio
async def test_reminders_skill_execution(db_session: AsyncSession) -> None:
    test_user = User(
        username="rem_skill_user",
        password_hash="dummy",
        role="owner",
    )
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    service = ReminderService(db_session=db_session)
    skill = RemindersSkill(reminder_service=service)

    ctx = SkillContext(request_id="req_rem_skill", user_id=test_user.id, provenance="direct")

    # Create via in_minutes
    create_res = await skill.execute(
        {"action": "create", "title": "Drink Water", "in_minutes": 5},
        ctx,
    )
    assert create_res.success is True
    reminder_id = create_res.data["id"]
    assert create_res.data["title"] == "Drink Water"

    # List
    list_res = await skill.execute({"action": "list", "status": "scheduled"}, ctx)
    assert list_res.success is True
    assert list_res.data["count"] >= 1

    # Get
    get_res = await skill.execute({"action": "get", "reminder_id": reminder_id}, ctx)
    assert get_res.success is True
    assert get_res.data["id"] == reminder_id

    # Cancel
    cancel_res = await skill.execute({"action": "cancel", "reminder_id": reminder_id}, ctx)
    assert cancel_res.success is True
    assert cancel_res.data["status"] == "cancelled"
