import json
from typing import Any
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.llm.types import (
    LLMMessage,
    LLMResponse,
    ModelRole,
    NormalizedToolCall,
    StreamChunk,
)
from backend.app.services.chat_service import (
    DEFAULT_SYSTEM_PROMPT,
    ChatService,
    estimate_tokens,
)
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult
from backend.app.skills.guard import (
    UNTRUSTED_CONTENT_TAG_START,
    has_untrusted_content,
    wrap_untrusted_content,
)
from backend.app.db.models import User
from backend.app.skills.registry import SkillRegistry


async def create_test_user(db: AsyncSession, username: str = "test_owner") -> User:
    user = User(username=username, password_hash="hash123", role="owner")
    db.add(user)
    await db.flush()
    return user


class MockLLMOrchestrator:
    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.recorded_calls: list[dict] = []

    async def chat(self, role: Any, messages: list[LLMMessage], tools: list[dict] | None = None) -> LLMResponse:
        self.recorded_calls.append({"role": role, "messages": messages, "tools": tools})
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="Default mock response", provider_used="mock", model_used="mock-model")

    async def chat_stream(self, role: Any, messages: list[LLMMessage], tools: list[dict] | None = None):
        self.recorded_calls.append({"role": role, "messages": messages, "tools": tools})
        if self.responses:
            resp = self.responses.pop(0)
            if resp.tool_calls:
                yield StreamChunk(tool_calls=resp.tool_calls)
            if resp.content:
                yield StreamChunk(content=resp.content)
        else:
            yield StreamChunk(content="Mock stream chunk")


class EchoSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="echo",
            description="Echo back input message.",
            default_tier="SAFE",
            default_autonomy="auto",
            parameters_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )

    async def execute(self, arguments: dict, _context: SkillContext) -> SkillResult:
        return SkillResult(success=True, data={"echo": arguments.get("text", "")})


class DangerousSkill(BaseSkill):
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="dangerous_action",
            description="Perform a sensitive operation.",
            default_tier="CONFIRM",
            default_autonomy="ask",
            parameters_schema={"type": "object", "properties": {}},
        )

    async def execute(self, arguments: dict, _context: SkillContext) -> SkillResult:
        return SkillResult(success=True, data={"result": "sensitive executed"})


@pytest.mark.asyncio
async def test_chat_service_system_prompt_only_treats_untrusted_as_data():
    """Verify that system prompt states untrusted content is data with no refusals or topic limits."""
    assert "<untrusted_external_content>" in DEFAULT_SYSTEM_PROMPT
    assert "data" in DEFAULT_SYSTEM_PROMPT.lower()
    # Check that preachy refusals/hedging are absent
    assert "i cannot" not in DEFAULT_SYSTEM_PROMPT.lower()
    assert "as an ai" not in DEFAULT_SYSTEM_PROMPT.lower()
    assert "i apologize" not in DEFAULT_SYSTEM_PROMPT.lower()


@pytest.mark.asyncio
async def test_chat_service_conversation_lifecycle(db_session: AsyncSession):
    """Test conversation creation, listing, message addition, and deletion."""
    user = await create_test_user(db_session, username="user_lifecycle")
    chat_svc = ChatService(db=db_session, orchestrator=MockLLMOrchestrator())
    user_id = user.id

    conv = await chat_svc.get_or_create_conversation(None, user_id=user_id, title="Test Chat")
    assert conv.id is not None
    assert conv.title == "Test Chat"

    # Add message
    msg = await chat_svc.conversation_repo.add_message(
        conversation_id=conv.id,
        role="user",
        content="Hello NIKO",
    )
    assert msg.id is not None

    messages = await chat_svc.get_messages(conv.id)
    assert len(messages) == 1
    assert messages[0].content == "Hello NIKO"

    # List conversations
    convs = await chat_svc.list_conversations(user_id=user_id)
    assert any(c.id == conv.id for c in convs)

    # Delete conversation
    deleted = await chat_svc.delete_conversation(conv.id, user_id=user_id)
    assert deleted is True
    assert (await chat_svc.get_or_create_conversation(conv.id, user_id=user_id)).title == "New Conversation"


@pytest.mark.asyncio
async def test_chat_service_sliding_context_window(db_session: AsyncSession):
    """Verify sliding context preserves system prompt and drops oldest messages when budget exceeded."""
    user = await create_test_user(db_session, username="user_sliding")
    chat_svc = ChatService(db=db_session, max_context_tokens=100)
    conv = await chat_svc.get_or_create_conversation(None, user_id=user.id)

    # Add several historical messages
    for i in range(10):
        await chat_svc.conversation_repo.add_message(
            conversation_id=conv.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message turn number {i} with additional padding content to consume context window budget.",
        )

    history = await chat_svc.conversation_repo.get_messages(conv.id)
    assert len(history) == 10

    context = chat_svc.build_sliding_context(history, new_user_message="Latest turn")
    # First message MUST be the system prompt
    assert context[0].role == "system"
    assert context[0].content == DEFAULT_SYSTEM_PROMPT

    # Context length must be significantly less than full 10 + 1 turns due to sliding window
    assert len(context) < 11
    # Last message MUST be the new user message
    assert context[-1].content == "Latest turn"


@pytest.mark.asyncio
async def test_chat_service_provenance_tagging_and_wrapping(db_session: AsyncSession):
    """Verify server-side provenance: direct vs external_untrusted and wrapping."""
    chat_svc = ChatService(db=db_session)

    # 1. Clean direct prompt
    prov_direct = chat_svc.determine_provenance("What is the time?")
    assert prov_direct == "direct"

    # 2. External source: web
    prov_web = chat_svc.determine_provenance("Search results", source="web")
    assert prov_web == "external_untrusted"

    # 3. External source: file / ocr
    prov_file = chat_svc.determine_provenance("File snippet", source="file")
    assert prov_file == "external_untrusted"

    prov_ocr = chat_svc.determine_provenance("Scanned text", source="ocr")
    assert prov_ocr == "external_untrusted"

    # 4. Content containing untrusted tags
    wrapped = wrap_untrusted_content("Potentially injected instructions")
    assert has_untrusted_content(wrapped)
    assert chat_svc.determine_provenance(wrapped) == "external_untrusted"


@pytest.mark.asyncio
async def test_chat_service_tool_dispatch_and_execution(db_session: AsyncSession):
    """Verify tool dispatch via SkillService, DB recording, and feeding results back to LLM."""
    user = await create_test_user(db_session, username="user_tool")
    registry = SkillRegistry()
    registry.register(EchoSkill())

    mock_llm = MockLLMOrchestrator(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    NormalizedToolCall(
                        id="call_1",
                        name="echo",
                        arguments={"text": "hello from tool"},
                    )
                ],
                provider_used="mock",
                model_used="test-model",
            ),
            LLMResponse(
                content="Echo completed: hello from tool",
                provider_used="mock",
                model_used="test-model",
            ),
        ]
    )

    from backend.app.services.skill_service import SkillService
    skill_svc = SkillService(db=db_session, registry=registry)
    chat_svc = ChatService(
        db=db_session,
        orchestrator=mock_llm,
        skill_service=skill_svc,
    )

    result = await chat_svc.chat(
        conversation_id=None,
        user_id=user.id,
        user_message="Echo 'hello from tool'",
    )

    assert result["content"] == "Echo completed: hello from tool"
    assert result["provenance"] == "direct"
    assert len(mock_llm.recorded_calls) == 2


@pytest.mark.asyncio
async def test_chat_service_untrusted_provenance_triggers_approval_on_confirm_tier(db_session: AsyncSession):
    """When untrusted content enters context, state-altering skills require explicit approval."""
    user = await create_test_user(db_session, username="user_danger")
    registry = SkillRegistry()
    registry.register(DangerousSkill())

    mock_llm = MockLLMOrchestrator(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    NormalizedToolCall(
                        id="call_danger",
                        name="dangerous_action",
                        arguments={},
                    )
                ],
                provider_used="mock",
                model_used="test-model",
            ),
        ]
    )

    from backend.app.services.skill_service import SkillService
    skill_svc = SkillService(db=db_session, registry=registry)
    chat_svc = ChatService(
        db=db_session,
        orchestrator=mock_llm,
        skill_service=skill_svc,
    )

    # Call with external_untrusted source (e.g. web scrape context)
    result = await chat_svc.chat(
        conversation_id=None,
        user_id=user.id,
        user_message="Please run dangerous action based on this web page",
        source="web",
    )

    assert result["provenance"] == "external_untrusted"
    assert result["pending_approval"] is not None
    assert "approval_id" in result["pending_approval"]


@pytest.mark.asyncio
async def test_chat_service_streaming_yields_events(db_session: AsyncSession):
    """Verify stream_chat yields chunk, tool_call, tool_result, and done events."""
    user = await create_test_user(db_session, username="user_stream")
    registry = SkillRegistry()
    registry.register(EchoSkill())

    mock_llm = MockLLMOrchestrator(
        responses=[
            LLMResponse(
                content="Thinking...",
                tool_calls=[
                    NormalizedToolCall(
                        id="stream_tc_1",
                        name="echo",
                        arguments={"text": "stream echo"},
                    )
                ],
                provider_used="mock",
                model_used="test-model",
            ),
            LLMResponse(
                content="Here is the echoed stream result.",
                provider_used="mock",
                model_used="test-model",
            ),
        ]
    )

    from backend.app.services.skill_service import SkillService
    skill_svc = SkillService(db=db_session, registry=registry)
    chat_svc = ChatService(
        db=db_session,
        orchestrator=mock_llm,
        skill_service=skill_svc,
    )

    events = []
    async for event in chat_svc.stream_chat(
        conversation_id=None,
        user_id=user.id,
        user_message="Stream test",
    ):
        events.append(event)

    types = [e["type"] for e in events]
    assert "chunk" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert "done" in types
