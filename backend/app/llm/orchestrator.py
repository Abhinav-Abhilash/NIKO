from collections.abc import AsyncIterator
from typing import Any

from backend.app.core.events import get_event_bus
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

FULL_FLASH_MODELS = {
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
}


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


def estimate_prompt_tokens_and_media(messages: list[LLMMessage]) -> tuple[int, bool]:
    """
    Cheap heuristic to estimate prompt tokens and detect image content.
    Roughly 4 characters per token. Over ~5,000 tokens or any image skips Groq.
    """
    total_chars = 0
    has_image = False
    for msg in messages:
        if msg.content:
            total_chars += len(msg.content)
            content_lower = msg.content.lower()
            if "data:image/" in content_lower or any(
                ext in content_lower for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", "image_url", "[image]"]
            ):
                has_image = True
    return max(1, total_chars // 4), has_image


def detect_hard_task(
    role: ModelRole | str,
    messages: list[LLMMessage],
    estimated_tokens: int,
    has_image: bool,
) -> bool:
    """
    Determines if a task warrants full Flash model usage (20 RPD) or reserve consumption.
    Never uses 20-RPD Flash models for simple small talk or basic queries.
    """
    role_str = role.value if isinstance(role, ModelRole) else str(role).lower()
    if role_str in ("code", "search", "vision_long"):
        return True
    if has_image or estimated_tokens > 1500:
        return True

    last_content = ""
    for msg in reversed(messages):
        if msg.role == "user" and msg.content:
            last_content = msg.content.lower()
            break

    complex_markers = {
        "complex", "debug", "architect", "algorithm", "solve", "hard", "refactor",
        "diagnose", "optimize", "benchmark", "analysis", "compare", "implement"
    }
    return any(marker in last_content for marker in complex_markers)


async def _notify_model_unavailable(provider: str, model: str, reason: str = "HTTP 404/410") -> None:
    model_discovery.mark_model_unavailable(provider, model, duration_hours=6.0, reason=reason)
    try:
        event_bus = get_event_bus()
        await event_bus.publish(
            "llm",
            "model_unavailable",
            {
                "provider": provider,
                "model": model,
                "duration_hours": 6.0,
                "reason": reason,
            },
        )
    except Exception:
        pass


class LLMOrchestrator:
    """
    Manages multi-provider execution with:
    - Role-based target sequencing (fast, coder, vision_long)
    - Token/image routing heuristics (>5000 tokens or image skips Groq)
    - Flash ladder sequencing (3.8 -> 3.7 -> 3.5 -> Flash-Lite)
    - Gated full Flash models preserving 20 RPD quotas strictly for hard tasks
    - Predictive rate-limit cooldown with Midnight Pacific resets and reserves
    - Dynamic discovery with missing-model skipping and 6h 404/410 gating
    - Mid-turn failover across providers
    - Tool call and context pruning
    """

    def __init__(
        self,
        provider_keys: dict[str, str] | None = None,
        roles_config: ModelRolesConfig | None = None,
    ) -> None:
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
        Skips missing models, cooled down models, and routes based on token/media heuristics.
        """
        role_str = role.value if isinstance(role, ModelRole) else role.lower()
        targets = self.roles_config.get_role_targets(role)
        prepared_messages = self._prepare_messages_for_context(messages, max_tool_tokens)
        estimated_tokens, has_image = estimate_prompt_tokens_and_media(prepared_messages)
        is_hard = detect_hard_task(role, prepared_messages, estimated_tokens, has_image)
        attempts: list[dict[str, str]] = []

        for target in targets:
            provider = self._get_provider_instance(target.provider)
            if not provider:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "no_api_key"})
                continue

            # Heuristic routing: over ~5000 tokens or any image skips Groq
            if target.provider == "groq" and (estimated_tokens > 5000 or has_image):
                logger.info(
                    "Skipping Groq target due to routing heuristics",
                    provider=target.provider,
                    model=target.model,
                    estimated_tokens=estimated_tokens,
                    has_image=has_image,
                )
                attempts.append({
                    "target": f"{target.provider}/{target.model}",
                    "status": f"skipped_heuristic (tokens={estimated_tokens}, has_image={has_image})"
                })
                continue

            # Full Flash preservation: only use full Flash for hard tasks, never for small talk
            if target.provider == "gemini" and target.model in FULL_FLASH_MODELS and not is_hard:
                logger.info(
                    "Preserving full Flash model for hard tasks; skipping for standard chat",
                    provider=target.provider,
                    model=target.model,
                )
                attempts.append({
                    "target": f"{target.provider}/{target.model}",
                    "status": "skipped_not_hard_task (full Flash preserved for code/vision/complex tasks)"
                })
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

            # Check predictive cooldown & hard-task reserve
            is_cooled, reason, remaining = cooldown_tracker.is_cooled_down(
                target.provider, target.model, is_hard_task=is_hard
            )
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
                await _notify_model_unavailable(target.provider, target.model, reason=f"404/410: {e}")
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
        role_str = role.value if isinstance(role, ModelRole) else role.lower()
        targets = self.roles_config.get_role_targets(role)
        prepared_messages = self._prepare_messages_for_context(messages, max_tool_tokens)
        estimated_tokens, has_image = estimate_prompt_tokens_and_media(prepared_messages)
        is_hard = detect_hard_task(role, prepared_messages, estimated_tokens, has_image)
        attempts: list[dict[str, str]] = []

        for target in targets:
            provider = self._get_provider_instance(target.provider)
            if not provider:
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "no_api_key"})
                continue

            # Heuristic routing: over ~5000 tokens or any image skips Groq
            if target.provider == "groq" and (estimated_tokens > 5000 or has_image):
                logger.info(
                    "Skipping Groq target due to routing heuristics",
                    provider=target.provider,
                    model=target.model,
                    estimated_tokens=estimated_tokens,
                    has_image=has_image,
                )
                attempts.append({
                    "target": f"{target.provider}/{target.model}",
                    "status": f"skipped_heuristic (tokens={estimated_tokens}, has_image={has_image})"
                })
                continue

            # Full Flash preservation: only use full Flash for hard tasks, never for small talk
            if target.provider == "gemini" and target.model in FULL_FLASH_MODELS and not is_hard:
                logger.info(
                    "Preserving full Flash model for hard tasks; skipping for standard chat",
                    provider=target.provider,
                    model=target.model,
                )
                attempts.append({
                    "target": f"{target.provider}/{target.model}",
                    "status": "skipped_not_hard_task (full Flash preserved for code/vision/complex tasks)"
                })
                continue

            if not model_discovery.is_model_available(target.provider, target.model):
                attempts.append({"target": f"{target.provider}/{target.model}", "status": "missing_or_404"})
                continue

            is_cooled, reason, remaining = cooldown_tracker.is_cooled_down(
                target.provider, target.model, is_hard_task=is_hard
            )
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
                await _notify_model_unavailable(target.provider, target.model, reason=f"404/410: {e}")
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
