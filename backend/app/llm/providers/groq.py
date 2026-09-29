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

logger = get_logger("niko.llm.groq")


class GroqProvider(BaseLLMProvider):
    """
    Groq LPU provider implementing high-speed streaming and normalized tool calling.
    Uses OpenAI-compatible endpoint with rate limit header tracking.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def provider_name(self) -> str:
        return "groq"

    def _convert_messages_and_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        max_output_tokens: int | None = None,
        _reasoning_effort: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        openai_msgs: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                openai_msgs.append({"role": "system", "content": msg.content})
            elif msg.role == "user":
                openai_msgs.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                m: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    m["tool_calls"] = [
                        {
                            "id": tc.id or f"call_{uuid.uuid4().hex[:12]}",
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                openai_msgs.append(m)
            elif msg.role == "tool":
                openai_msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "call_unknown",
                        "name": msg.name or "tool",
                        "content": msg.content,
                    }
                )

        body: dict[str, Any] = {
            "messages": openai_msgs,
            "temperature": temperature,
        }

        if max_output_tokens:
            body["max_tokens"] = max_output_tokens

        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {}),
                    },
                }
                for t in tools
            ]

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
        body["model"] = model
        body["stream"] = True

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Track active tool calls being streamed
        pending_tool_calls: dict[int, dict[str, Any]] = {}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code == 429:
                    retry_header = response.headers.get("retry-after") or "60"
                    retry_sec = float(retry_header) if retry_header.isdigit() else 60.0
                    raise ProviderRateLimitError("groq", model, retry_after=retry_sec)
                elif response.status_code == 404:
                    raise ProviderModelNotFoundError("groq", model)
                elif response.status_code in (401, 403):
                    raise ProviderAuthError("groq")
                elif response.status_code >= 400:
                    err_text = await response.aread()
                    raise ProviderRateLimitError(
                        "groq", model, retry_after=10.0, message=f"Groq API error ({response.status_code}): {err_text.decode('utf-8', errors='ignore')}"
                    )

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk_json.get("choices", [])
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    delta_text = delta.get("content") or ""

                    # Assemble streaming tool calls
                    tool_calls_delta = delta.get("tool_calls", [])
                    for tc in tool_calls_delta:
                        idx = tc.get("index", 0)
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments_str": tc.get("function", {}).get("arguments", ""),
                            }
                        else:
                            if "id" in tc and tc["id"]:
                                pending_tool_calls[idx]["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if "name" in fn:
                                pending_tool_calls[idx]["name"] += fn["name"]
                            if "arguments" in fn:
                                pending_tool_calls[idx]["arguments_str"] += fn["arguments"]

                    emitted_tools: list[NormalizedToolCall] | None = None
                    if finish_reason == "tool_calls" or (finish_reason and pending_tool_calls):
                        emitted_tools = []
                        for _, p in sorted(pending_tool_calls.items()):
                            try:
                                args = json.loads(p["arguments_str"]) if p["arguments_str"] else {}
                            except Exception:
                                args = {}
                            emitted_tools.append(
                                NormalizedToolCall(
                                    id=p["id"],
                                    name=p["name"],
                                    arguments=args,
                                )
                            )
                        pending_tool_calls.clear()

                    yield StreamChunk(
                        content=delta_text,
                        tool_calls=emitted_tools,
                        finish_reason=finish_reason,
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
        body["model"] = model
        body["stream"] = False

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, headers=headers, json=body)
            if res.status_code == 429:
                retry_header = res.headers.get("retry-after") or "60"
                retry_sec = float(retry_header) if retry_header.isdigit() else 60.0
                raise ProviderRateLimitError("groq", model, retry_after=retry_sec)
            elif res.status_code == 404:
                raise ProviderModelNotFoundError("groq", model)
            elif res.status_code in (401, 403):
                raise ProviderAuthError("groq")
            elif res.status_code >= 400:
                raise ProviderRateLimitError(
                    "groq", model, retry_after=10.0, message=f"Groq API error ({res.status_code}): {res.text}"
                )

            data = res.json()
            choices = data.get("choices", [])
            content_text = ""
            tool_calls: list[NormalizedToolCall] = []
            finish_reason = "stop"

            if choices:
                choice = choices[0]
                finish_reason = choice.get("finish_reason", "stop")
                msg_obj = choice.get("message", {})
                content_text = msg_obj.get("content") or ""
                raw_tools = msg_obj.get("tool_calls") or []
                for rt in raw_tools:
                    fn = rt.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    tool_calls.append(
                        NormalizedToolCall(
                            id=rt.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                            name=fn.get("name", ""),
                            arguments=args,
                        )
                    )

            usage = data.get("usage", {})
            return LLMResponse(
                content=content_text,
                tool_calls=tool_calls,
                model_used=model,
                provider_used="groq",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=finish_reason,
            )
