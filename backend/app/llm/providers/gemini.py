import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.app.core.logging import get_logger
from backend.app.llm.base import BaseLLMProvider
from backend.app.llm.exceptions import (
    ProviderAuthError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
)
from backend.app.llm.types import LLMMessage, LLMResponse, NormalizedToolCall, StreamChunk

logger = get_logger("niko.llm.gemini")


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini provider implementing streaming and normalized tool calling.
    Handles stable system prompt caching and Gemini part conversion.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _convert_messages_and_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        _reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        system_instruction_parts: list[dict[str, Any]] = []
        contents: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    system_instruction_parts.append({"text": msg.content})
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                parts: list[dict[str, Any]] = []
                if msg.content:
                    parts.append({"text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(
                            {
                                "functionCall": {
                                    "name": tc.name,
                                    "args": tc.arguments,
                                }
                            }
                        )
                if parts:
                    contents.append({"role": "model", "parts": parts})
            elif msg.role == "tool":
                # Gemini functionResponse
                name = msg.name or "tool"
                try:
                    res_val = json.loads(msg.content) if msg.content.startswith("{") else {"result": msg.content}
                except Exception:
                    res_val = {"result": msg.content}
                contents.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": name,
                                    "response": res_val,
                                }
                            }
                        ],
                    }
                )

        body: dict[str, Any] = {"contents": contents}

        if system_instruction_parts:
            # Stable system instruction for efficient prompt caching
            body["systemInstruction"] = {"parts": system_instruction_parts}

        # Generation config
        gen_config: dict[str, Any] = {"temperature": temperature}
        if max_output_tokens:
            gen_config["maxOutputTokens"] = max_output_tokens
        body["generationConfig"] = gen_config

        # Tools declaration
        if tools:
            func_decls = []
            for t in tools:
                schema = t.get("parameters", {})
                func_decls.append(
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": schema,
                    }
                )
            if func_decls:
                body["tools"] = [{"functionDeclarations": func_decls}]

        return body

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        body = self._convert_messages_and_tools(
            messages, tools, max_output_tokens, reasoning_effort, temperature
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={self.api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=body) as response:
                if response.status_code == 429:
                    retry_header = response.headers.get("retry-after") or "60"
                    retry_sec = float(retry_header) if retry_header.isdigit() else 60.0
                    raise ProviderRateLimitError("gemini", model, retry_after=retry_sec)
                elif response.status_code == 404:
                    raise ProviderModelNotFoundError("gemini", model)
                elif response.status_code in (401, 403):
                    raise ProviderAuthError("gemini")
                elif response.status_code >= 400:
                    err_text = await response.aread()
                    raise ProviderRateLimitError(
                        "gemini", model, retry_after=10.0, message=f"Gemini API error ({response.status_code}): {err_text.decode('utf-8', errors='ignore')}"
                    )

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):].strip()
                    if not data_str:
                        continue
                    try:
                        chunk_json = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    candidates = chunk_json.get("candidates", [])
                    if not candidates:
                        continue
                    candidate = candidates[0]
                    content_obj = candidate.get("content", {})
                    parts = content_obj.get("parts", [])

                    delta_text = ""
                    tool_calls: list[NormalizedToolCall] = []

                    for part in parts:
                        if "text" in part:
                            delta_text += part["text"]
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            tool_calls.append(
                                NormalizedToolCall(
                                    id=f"call_{uuid.uuid4().hex[:12]}",
                                    name=fc.get("name", ""),
                                    arguments=fc.get("args", {}),
                                )
                            )

                    finish_reason = candidate.get("finishReason")
                    usage_meta = chunk_json.get("usageMetadata", {})
                    usage = (
                        {
                            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                            "total_tokens": usage_meta.get("totalTokenCount", 0),
                        }
                        if usage_meta
                        else None
                    )

                    yield StreamChunk(
                        content=delta_text,
                        tool_calls=tool_calls if tool_calls else None,
                        finish_reason=finish_reason,
                        usage=usage,
                    )

    async def chat_complete(
        self,
        messages: list[LLMMessage],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        body = self._convert_messages_and_tools(
            messages, tools, max_output_tokens, reasoning_effort, temperature
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json=body)
            if res.status_code == 429:
                retry_header = res.headers.get("retry-after") or "60"
                retry_sec = float(retry_header) if retry_header.isdigit() else 60.0
                raise ProviderRateLimitError("gemini", model, retry_after=retry_sec)
            elif res.status_code == 404:
                raise ProviderModelNotFoundError("gemini", model)
            elif res.status_code in (401, 403):
                raise ProviderAuthError("gemini")
            elif res.status_code >= 400:
                raise ProviderRateLimitError(
                    "gemini", model, retry_after=10.0, message=f"Gemini API error ({res.status_code}): {res.text}"
                )

            data = res.json()
            candidates = data.get("candidates", [])
            content_text = ""
            tool_calls: list[NormalizedToolCall] = []
            finish_reason = "stop"

            if candidates:
                cand = candidates[0]
                finish_reason = cand.get("finishReason", "stop")
                parts = cand.get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        content_text += part["text"]
                    if "functionCall" in part:
                        fc = part["functionCall"]
                        tool_calls.append(
                            NormalizedToolCall(
                                id=f"call_{uuid.uuid4().hex[:12]}",
                                name=fc.get("name", ""),
                                arguments=fc.get("args", {}),
                            )
                        )

            usage = data.get("usageMetadata", {})
            return LLMResponse(
                content=content_text,
                tool_calls=tool_calls,
                model_used=model,
                provider_used="gemini",
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=usage.get("candidatesTokenCount", 0),
                finish_reason=finish_reason,
            )
