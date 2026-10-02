# ADR 0005: Model Roles, Sequential Multi-Provider Fallback & Quota Resilience

## Status
Accepted

## Context
NIKO requires zero paid subscriptions and zero local GPU/RAM footprint from local LLM runners (e.g. Ollama). It must operate reliably within third-party free-tier quotas across Google Gemini, Groq, and OpenRouter without leaking API keys, exceeding rate limits, or failing user tasks when an upstream provider throttles or encounters outages.

## Decision
1. **True AI Studio Quotas & Flash Ladder**:
   - Google AI Studio rate-limit page (read 2026-10-02) confirms:
     - `gemini-3.5-flash-lite`: 15 RPM, 500 RPD, 250K TPM
     - `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.5-flash`: 5 RPM, 20 RPD, 250K TPM each (separate pools)
     - `gemini-2.0-flash`, `gemini-2.0-flash-lite`: 0/0/0 (dead)
   - Role implementation:
     - `fast` (light + chat): Groq `openai/gpt-oss-20b` for short prompts (<5k tokens), then `gemini-3.5-flash-lite`, and `openrouter/free`. Never uses 20-RPD Flash models for small talk.
     - `coder` (code): Groq `openai/gpt-oss-120b` for short snippets. For long code (>5k tokens) or when Groq is out: Flash ladder `gemini-3.8-flash` $\to$ `gemini-3.7-flash` $\to$ `gemini-3.5-flash` $\to$ `gemini-3.5-flash-lite` $\to$ `cohere/north-mini-code:free` $\to$ `openrouter/free`.
     - `vision_long` (search + image/long input): `gemini-3.5-flash-lite` $\to$ `gemini-3.8-flash` $\to$ `gemini-3.7-flash` $\to$ `gemini-3.5-flash`.

2. **Midnight Pacific Daily Reset & 4-Request Reserve**:
   - Per-model daily request counters reset at 00:00 Pacific Time (`America/Los_Angeles`).
   - On 20-RPD Flash models, the last 4 requests are reserved strictly for complex tasks. Non-hard tasks automatically step down to Flash-Lite (500 RPD) when usage reaches 16/20.

3. **Sequential Lazy Fallback & Heuristic Skipping**:
   - Multi-provider queries are never dispatched in parallel (conserving quota). The primary model is queried first; fallback models are engaged sequentially only upon rate limits (HTTP 429), auth failures, or model unavailability.

4. **Live Model Discovery & 6-Hour Runtime Deprecation Gating**:
   - Model endpoints are queried at startup via list-models endpoints without generation calls.
   - Runtime HTTP 404 or 410 errors mark the model unavailable for 6 hours, emit a bus event, and promote the next candidate.

5. **Quota-Exhaustion Deferred Queue & Cooldown Banner**:
   - When all candidate providers for a role enter cooldown, requests enter an in-memory deferred queue (`DeferredQueue`).
   - A real-time cooldown banner event is published on the event bus and WebSocket hub.
   - When the shortest cooldown window expires, the deferred queue worker automatically retries and fulfills queued requests.

6. **Key Redaction & Header-Based Authentication**:
   - Gemini API keys are sent strictly in the `x-goog-api-key` header (never in query URLs).
   - Provider keys and tokens are scrubbed from structlog, error traces, and uvicorn access/error logs.
   - `httpx` and `httpcore` loggers are pinned to `WARNING` to prevent debug payload header leaks.

## Consequences
- **Positive**: Complete compliance with verified AI Studio quotas; protection of scarce 20-RPD Flash models for hard tasks; smooth degradation to Flash-Lite (500 RPD); zero key leaks in logs.
- **Negative**: Long multi-turn coding sessions may exhaust Flash models and fallback to Flash-Lite until Midnight Pacific reset.
