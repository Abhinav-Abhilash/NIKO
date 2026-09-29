import json
import time
from typing import Any, AsyncIterator
import pytest
from unittest.mock import AsyncMock, patch

from backend.app.llm.base import BaseLLMProvider
from backend.app.llm.cooldown import PredictiveCooldownTracker
from backend.app.llm.defaults import get_default_roles_config
from backend.app.llm.discovery import ModelDiscoveryService
from backend.app.llm.exceptions import (
    AllProvidersExhaustedError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
)
from backend.app.llm.orchestrator import LLMOrchestrator, prune_tool_output
from backend.app.llm.router import route_prompt_role
from backend.app.llm.types import (
    LLMMessage,
    LLMResponse,
    ModelRole,
    ModelRolesConfig,
    NormalizedToolCall,
    RoleModelTarget,
    StreamChunk,
)


class MockProvider(BaseLLMProvider):
    def __init__(self, name: str, behavior: str = "success"):
        self.name = name
        self.behavior = behavior
        self.calls: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return self.name

    async def chat_complete(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self.calls.append({"model": model, "messages": messages})
        if self.behavior == "429":
            raise ProviderRateLimitError(self.name, model, retry_after=30.0)
        elif self.behavior == "404":
            raise ProviderModelNotFoundError(self.name, model)
        elif self.behavior == "error":
            raise RuntimeError("Upstream connection failure")

        return LLMResponse(
            content=f"Response from {self.name}/{model}",
            tool_calls=[],
            model_used=model,
            provider_used=self.name,
            input_tokens=10,
            output_tokens=20,
            finish_reason="stop",
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        self.calls.append({"model": model, "messages": messages})
        if self.behavior == "429":
            raise ProviderRateLimitError(self.name, model, retry_after=30.0)
        elif self.behavior == "404":
            raise ProviderModelNotFoundError(self.name, model)

        yield StreamChunk(content=f"Stream from {self.name}/{model}")


@pytest.mark.asyncio
async def test_role_fallback_order():
    """Verify orchestrator tries targets in exact role order on failure/429."""
    config = ModelRolesConfig(
        chat=[
            RoleModelTarget(provider="gemini", model="gemini-2.0-flash"),
            RoleModelTarget(provider="groq", model="openai/gpt-oss-120b"),
            RoleModelTarget(provider="openrouter", model="openrouter/free"),
        ]
    )

    gemini_mock = MockProvider("gemini", behavior="429")
    groq_mock = MockProvider("groq", behavior="success")
    openrouter_mock = MockProvider("openrouter", behavior="success")

    orchestrator = LLMOrchestrator(
        provider_keys={"gemini": "k1", "groq": "k2", "openrouter": "k3"},
        roles_config=config,
    )
    orchestrator._providers["gemini"] = gemini_mock
    orchestrator._providers["groq"] = groq_mock
    orchestrator._providers["openrouter"] = openrouter_mock

    messages = [LLMMessage(role="user", content="Hello NIKO")]
    resp = await orchestrator.chat_complete(role=ModelRole.CHAT, messages=messages)

    # Gemini failed with 429, so Groq succeeded
    assert resp.provider_used == "groq"
    assert resp.model_used == "openai/gpt-oss-120b"
    assert len(gemini_mock.calls) == 1
    assert len(groq_mock.calls) == 1
    assert len(openrouter_mock.calls) == 0


@pytest.mark.asyncio
async def test_missing_model_skip():
    """Verify that models not discovered or 404ing are skipped with warning without failing."""
    config = ModelRolesConfig(
        light=[
            RoleModelTarget(provider="gemini", model="gemini-nonexistent"),
            RoleModelTarget(provider="groq", model="openai/gpt-oss-20b"),
        ]
    )

    gemini_mock = MockProvider("gemini", behavior="404")
    groq_mock = MockProvider("groq", behavior="success")

    orchestrator = LLMOrchestrator(
        provider_keys={"gemini": "k1", "groq": "k2"},
        roles_config=config,
    )
    orchestrator._providers["gemini"] = gemini_mock
    orchestrator._providers["groq"] = groq_mock

    messages = [LLMMessage(role="user", content="ping")]
    resp = await orchestrator.chat_complete(role=ModelRole.LIGHT, messages=messages)

    assert resp.provider_used == "groq"
    assert resp.model_used == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_all_providers_exhausted_raises():
    """Verify AllProvidersExhaustedError is raised if all candidates in sequence fail."""
    config = ModelRolesConfig(
        code=[
            RoleModelTarget(provider="gemini", model="gemini-2.0-flash"),
            RoleModelTarget(provider="groq", model="openai/gpt-oss-120b"),
        ]
    )

    gemini_mock = MockProvider("gemini", behavior="429")
    groq_mock = MockProvider("groq", behavior="error")

    orchestrator = LLMOrchestrator(
        provider_keys={"gemini": "k1", "groq": "k2"},
        roles_config=config,
    )
    orchestrator._providers["gemini"] = gemini_mock
    orchestrator._providers["groq"] = groq_mock

    messages = [LLMMessage(role="user", content="def solve(): pass")]
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await orchestrator.chat_complete(role=ModelRole.CODE, messages=messages)

    assert exc_info.value.role == "code"
    assert len(exc_info.value.attempts) == 2


def test_predictive_cooldown_tracker():
    """Verify predictive cooldown triggers BEFORE reaching the limit (at 90% quota)."""
    tracker = PredictiveCooldownTracker(predictive_threshold_ratio=0.90)

    # Gemini has rpm=15, 90% is 13 requests
    now = time.time()
    for _ in range(13):
        is_cool, _, _ = tracker.is_cooled_down("gemini", "gemini-2.0-flash", now=now)
        assert not is_cool
        tracker.record_success("gemini", "gemini-2.0-flash", input_tokens=10, output_tokens=10, now=now)

    # 14th request should trip predictive RPM cooldown
    is_cool, reason, remaining = tracker.is_cooled_down("gemini", "gemini-2.0-flash", now=now)
    assert is_cool
    assert "Predictive RPM threshold reached" in (reason or "")
    assert remaining > 0


def test_upstream_429_cooldown():
    """Verify real 429 response engages forced cooldown with Retry-After header."""
    tracker = PredictiveCooldownTracker()
    now = time.time()

    tracker.record_429("groq", "openai/gpt-oss-120b", retry_after_seconds=45.0, now=now)

    is_cool, reason, remaining = tracker.is_cooled_down("groq", "openai/gpt-oss-120b", now=now + 10)
    assert is_cool
    assert "Upstream 429" in (reason or "")
    assert 30 <= remaining <= 36


def test_heuristic_role_router():
    """Verify cheap heuristics correctly route code, search, light, and chat prompts."""
    # Code prompts
    assert route_prompt_role("def calculate_fibonacci(n):\n    return n") == ModelRole.CODE
    assert route_prompt_role("```python\nprint('hi')\n```") == ModelRole.CODE
    assert route_prompt_role("Please fix the AttributeError in my script") == ModelRole.CODE
    assert route_prompt_role("git commit -m 'feat: add stuff'") == ModelRole.CODE

    # Search prompts
    assert route_prompt_role("search the web for latest AI news") == ModelRole.SEARCH
    assert route_prompt_role("look up online what the weather in Tokyo is") == ModelRole.SEARCH
    assert route_prompt_role("check https://example.com and summarize it") == ModelRole.SEARCH

    # Light prompts
    assert route_prompt_role("hello") == ModelRole.LIGHT
    assert route_prompt_role("ping") == ModelRole.LIGHT
    assert route_prompt_role("what time is it?") == ModelRole.LIGHT
    assert route_prompt_role("good morning") == ModelRole.LIGHT

    # Chat prompts
    assert route_prompt_role("Can you explain how solar flares affect satellites?") == ModelRole.CHAT
    assert route_prompt_role("Write a creative bedtime story about a friendly robot.") == ModelRole.CHAT


def test_prune_tool_output_truncation():
    """Verify tool output is pruned with head-tail truncation when exceeding 1200 tokens (~4800 chars)."""
    short_output = "Short tool result: OK"
    assert prune_tool_output(short_output, max_tokens=1200) == short_output

    # 10,000 characters
    long_output = "A" * 5000 + "MIDDLE" + "Z" * 5000
    pruned = prune_tool_output(long_output, max_tokens=1200)
    assert len(pruned) < len(long_output)
    assert pruned.startswith("A" * 2400)
    assert pruned.endswith("Z" * 2400)
    assert "... [tool output truncated for context window" in pruned


@pytest.mark.asyncio
async def test_discovery_skips_unreachable():
    """Verify model discovery returns empty or skips gracefully if endpoint fails."""
    service = ModelDiscoveryService()

    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        gemini_models = await service.discover_gemini("test_key")
        assert gemini_models == []

        groq_models = await service.discover_groq("test_key")
        assert groq_models == []

        openrouter_models = await service.discover_openrouter()
        assert openrouter_models == ["openrouter/free"]
