# ADR 0005: Model Roles, Sequential Multi-Provider Fallback & Quota Resilience

## Status
Accepted

## Context
NIKO requires zero paid subscriptions and zero local GPU/RAM footprint from local LLM runners (e.g. Ollama). It must operate reliably within third-party free-tier quotas across Google Gemini, Groq, and OpenRouter without leaking API keys, exceeding rate limits, or failing user tasks when an upstream provider throttles or encounters outages.

## Decision
1. **Task-Specific Model Roles & Approved Lineup**:
   - Roles implement 3 core jobs with intelligent content-length/type routing:
     - `fast` (light + chat): Groq `openai/gpt-oss-20b` for short prompts (<5k tokens), then `gemini-3.5-flash-lite`, `gemini-flash-lite-latest` (backup), and `openrouter/free`.
     - `coder` (code): Groq `openai/gpt-oss-120b` for short snippets, then `gemini-3.8-flash` for long code (>5k tokens), `gemini-flash-latest` (backup), `cohere/north-mini-code:free`, and `openrouter/free`.
     - `vision_long` (search + image/long input): `gemini-3.5-flash-lite` $\to$ `gemini-3.8-flash` $\to$ `gemini-flash-latest`.
   - Heuristic Routing: Prompts over ~5,000 estimated tokens or containing image data automatically bypass Groq and route directly to Gemini.
   - Reasoning settings: Minimal thinking level for `fast`, moderate thinking budget (1024) for `coder`.

2. **Sequential Lazy Fallback & Heuristic Skipping**:
   - Multi-provider queries are never dispatched in parallel (conserving quota). The primary model is queried first; fallback models are engaged sequentially only upon rate limits (HTTP 429), auth failures, or model unavailability.

3. **Live Model Discovery & 6-Hour Runtime Deprecation Gating**:
   - Model endpoints are queried at startup via list-models endpoints without generation calls.
   - Runtime HTTP 404 or 410 errors mark the model unavailable for 6 hours, emit a bus event, and promote the next candidate.

4. **Predictive Cooldown Tracker**:
   - Request and token tallies are maintained in rolling minute and daily windows.
   - Predictive cooldown engages at 90% of RPM, RPD, TPM, or TPD before an upstream HTTP 429 error occurs.
   - Upstream HTTP 429 responses and `Retry-After` headers immediately apply exponential backoff.

5. **Quota-Exhaustion Deferred Queue & Cooldown Banner**:
   - When all candidate providers for a role enter cooldown, requests enter an in-memory deferred queue (`DeferredQueue`).
   - A real-time cooldown banner event (`all providers cooling down, shortest reset in ...`) is published on the event bus and WebSocket hub.
   - When the shortest cooldown window expires, the deferred queue worker automatically retries and fulfills queued requests, clearing the banner.

6. **Context Sliding Window & Tool Output Pruning**:
   - The system prompt is pinned at index 0 and strictly instructs the LLM that untrusted external content is raw data.
   - Verbose tool outputs (search results, file contents, OCR) are pruned to 1,200 tokens using head-tail truncation.
   - Context history slides older turns out when token budgets are reached.

7. **Key Redaction & Header-Based Authentication**:
   - Gemini API keys are sent strictly in the `x-goog-api-key` header (never in query URLs).
   - Provider keys and tokens are scrubbed from structlog, error traces, and uvicorn access/error logs using regex filters and dynamic token registration.
   - `httpx` and `httpcore` loggers are pinned to `WARNING` to prevent debug payload header leaks.

## Consequences
- **Positive**: High availability across zero-cost free tiers; graceful degradation under heavy load; zero key leaks in logs; seamless user experience via automatic retry and routing heuristics.
- **Negative**: Temporary queuing delays when upstream free-tier quotas are entirely saturated.
