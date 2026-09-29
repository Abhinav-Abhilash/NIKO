from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from backend.app.llm.types import LLMMessage, LLMResponse, StreamChunk


class BaseLLMProvider(ABC):
    """
    Abstract base interface for all LLM providers in NIKO.
    Enforces normalized message inputs, normalized tool definitions,
    and unified streaming/complete response structures.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. gemini, groq, openrouter)."""
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        """Stream response chunks from the model with delta text or normalized tool calls."""
        pass

    @abstractmethod
    async def chat_complete(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Non-streaming complete chat invocation."""
        pass
