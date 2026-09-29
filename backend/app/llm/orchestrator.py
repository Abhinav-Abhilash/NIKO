from collections.abc import AsyncIterator
from typing import Any

from backend.app.core.logging import get_logger, register_sensitive_token
from backend.app.llm.base import BaseLLMProvider
from backend.app.llm.cooldown import cooldown_tracker
from backend.app.llm.defaults import get_default_roles_config
from backend.app.llm.discovery import model_discovery
from backend.app.llm.exceptions import (
    AllProvidersExhaustedError,
    ProviderAuthError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
)
from backend.app.llm.providers.gemini import GeminiProvider
from backend.app.llm.providers.groq import GroqProvider
from backend.app.llm.providers.openrouter import OpenRouterProvider
from backend.app.llm.types import (
    LLMMessage,
    LLMResponse,
    ModelRole,
    ModelRolesConfig,
    StreamChunk,
)

logger = get_logger("niko.llm.orchestrator")


def prune_tool_output(content: str, max_tokens: int = 1200) -> str:
    """
    Prunes long tool output in context using head-tail truncation.
    Roughly 4 characters per token: max_chars = max_tokens * 4 (~4800 chars).
    Retains first half and last half with an explicit truncation marker.
    """
    max_chars = max_tokens * 4
    if len(content) <= max_chars:
        return content

    half = max_chars // 2
    head = content[:half]
    tail = content[-half:]
    truncated_msg = f"\n\n... [tool output truncated for context window ({len(content)} chars)] ...\n\n"
    return head + truncated_msg + tail


class LLMOrchestrator:
    """
    Manages multi-provider execution with:
    - Role-based target sequencing (light, chat, code, search)
    - Predictive rate-limit cooldown
    - Dynamic discovery with missing-model skipping
    - Mid-turn failover across providers
    - Tool call and context pruning
    """

    def __init__(
        self,
        provider_keys: dict[str, str] | None = None,
        roles_config: ModelRolesConfig | None = None,
    ):
        self.provider_keys = provider_keys or {}
        self.roles_config = roles_config or get_default_roles_config()
        self._providers: dict[str, BaseLLMProvider] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        self._providers.clear()
        if "gemini" in self.provider_keys and self.provider_keys["gemini"]:
            register_sensitive_token(self.provider_keys["gemini"])
            self._providers["gemini"] = GeminiProvider(self.provider_keys["gemini"])
        if "groq" in self.provider_keys and self.provider_keys["groq"]:
            register_sensitive_token(self.provider_keys["groq"])
            self._providers["groq"] = GroqProvider(self.provider_keys["groq"])
        if "openrouter" in self.provider_keys and self.provider_keys["openrouter"]:
            register_sensitive_token(self.provider_keys["openrouter"])
            self._providers["openrouter"] = OpenRouterProvider(self.provider_keys["openrouter"])

    def set_provider_key(self, provider: str, api_key: str) -> None:
        register_sensitive_token(api_key)
        self.provider_keys[provider.lower()] = api_key
        self._init_providers()

    def set_roles_config(self, config: ModelRolesConfig) -> None:
        self.roles_config = config

    def _get_provider_instance(self, provider_name: str) -> BaseLLMProvider | None:
        return self._providers.get(provider_name.lower())

    def _prepare_messages_for_context(
        self, messages: list[LLMMessage], max_tool_tokens: int = 1200
    ) -> list[LLMMessage]:
        """Apply head-tail truncation to tool messages in context."""
        pruned_messages: list[LLMMessage] = []
        for msg in messages:
            if msg.role == "tool" and msg.content:
                pruned_content = prune_tool_output(msg.content, max_tokens=max_tool_tokens)
                pruned_messages.append(
                    LLMMessage(
                        role=msg.role,
                        content=pruned_content,
                        tool_calls=msg.tool_calls,
                        tool_call_id=msg.tool_call_id,
                        name=msg.name,
                    )
                )
            else:
                pruned_messages.append(msg)
        return pruned_messages

    async def chat_complete(
        self,
        role: ModelRole | str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        max_tool_tokens: int = 1200,
    ) -> LLMResponse:
        """
        Execute chat completion with role-based sequential fallback across providers.
        Skips missing models and models in predictive/429 cooldown.
        """
        role_str = role.value if isinstance(role, ModelRole) else str(role).lower()
        targets = self.roles_config.get_role_targets(role)
        prepared_messages = self._prepare_messages_for_context(messages, max_tool_tokens)
        attempts: list[dict[str, str]] = []

        for target in targets:
            provider = self._get_provider_instance(target.provider)
            if not provider:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "no_api_key"})
                continue

            # Check dynamic discovery
            if not model_discovery.is_model_available(target.provider, target.model):
                logger.warning(
                    "Skipping unavailable or missing model in fallback sequence",
                    provider=target.provider,
                    model=target.model,
                )
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "missing_or_404"})
                continue

            # Check predictive cooldown
            is_cooled, reason, remaining = cooldown_tracker.is_cooled_down(target.provider, target.model)
            if is_cooled:
                logger.warning(
                    "Skipping cooled down model in fallback sequence",
                    provider=target.provider,
                    model=target.model,
                    reason=reason,
                    remaining_seconds=remaining,
                )
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"cooldown: {reason}"})
                continue

            # Attempt provider execution
            try:
                logger.info(
                    "Executing LLM invocation",
                    role=role_str,
                    provider=target.provider,
                    model=target.model,
                )
                response = await provider.chat_complete(
                    messages=prepared_messages,
                    model=target.model,
                    tools=tools,
                    max_output_tokens=target.max_output_tokens,
                    reasoning_effort=target.reasoning_effort,
                    temperature=target.temperature,
                )
                # Record successful usage
                cooldown_tracker.record_success(
                    provider=target.provider,
                    model=target.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
                return response
            except ProviderRateLimitError as e:
                cooldown_tracker.record_429(target.provider, target.model, retry_after_seconds=e.retry_after)
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"429: {e}"})
                continue
            except ProviderModelNotFoundError as e:
                model_discovery.mark_model_missing(target.provider, target.model)
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"404: {e}"})
                continue
            except ProviderAuthError as e:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"auth_error: {e}"})
                continue
            except Exception as e:
                logger.error(
                    "Provider execution failed, falling back to next target",
                    provider=target.provider,
                    model=target.model,
                    error=str(e),
                )
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"error: {str(e)}"})
                continue

        # If all exhausted
        logger.error("All providers and models exhausted for role", role=role_str, attempts=attempts)
        raise AllProvidersExhaustedError(role=role_str, attempts=attempts)

    # Alias for non-streaming chat complete
    chat = chat_complete


    async def chat_stream(
        self,
        role: ModelRole | str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        max_tool_tokens: int = 1200,
    ) -> AsyncIterator[StreamChunk]:
        """
        Execute streaming chat with role-based sequential fallback across providers.
        """
        role_str = role.value if isinstance(role, ModelRole) else str(role).lower()
        targets = self.roles_config.get_role_targets(role)
        prepared_messages = self._prepare_messages_for_context(messages, max_tool_tokens)
        attempts: list[dict[str, str]] = []

        for target in targets:
            provider = self._get_provider_instance(target.provider)
            if not provider:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "no_api_key"})
                continue

            if not model_discovery.is_model_available(target.provider, target.model):
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "missing_or_404"})
                continue

            is_cooled, reason, remaining = cooldown_tracker.is_cooled_down(target.provider, target.model)
            if is_cooled:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"cooldown: {reason}"})
                continue

            try:
                # Test opening stream
                stream = provider.chat_stream(
                    messages=prepared_messages,
                    model=target.model,
                    tools=tools,
                    max_output_tokens=target.max_output_tokens,
                    reasoning_effort=target.reasoning_effort,
                    temperature=target.temperature,
                )
                total_in = 0
                total_out = 0
                async for chunk in stream:
                    if chunk.usage:
                        total_in = chunk.usage.get("prompt_tokens", 0)
                        total_out = chunk.usage.get("completion_tokens", 0)
                    elif chunk.content:
                        total_out += 1
                    yield chunk

                # Record success
                cooldown_tracker.record_success(
                    provider=target.provider,
                    model=target.model,
                    input_tokens=total_in,
                    output_tokens=total_out,
                )
                return
            except ProviderRateLimitError as e:
                cooldown_tracker.record_429(target.provider, target.model, retry_after_seconds=e.retry_after)
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"429: {e}"})
                continue
            except ProviderModelNotFoundError as e:
                model_discovery.mark_model_missing(target.provider, target.model)
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"404: {e}"})
                continue
            except Exception as e:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": f"error: {str(e)}"})
                continue

        raise AllProvidersExhaustedError(role=role_str, attempts=attempts)


_orchestrator_instance: LLMOrchestrator | None = None


def get_llm_orchestrator(
    provider_keys: dict[str, str] | None = None,
    roles_config: ModelRolesConfig | None = None,
) -> LLMOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = LLMOrchestrator(
            provider_keys=provider_keys,
            roles_config=roles_config,
        )
    else:
        if provider_keys:
            for p, k in provider_keys.items():
                _orchestrator_instance.set_provider_key(p, k)
        if roles_config:
            _orchestrator_instance.set_roles_config(roles_config)
    return _orchestrator_instance

