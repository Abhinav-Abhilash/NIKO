# ADR 0005: Model Roles, Sequential Multi-Provider Fallback & Quota Resilience

## Status
Accepted

## Context
NIKO requires zero paid subscriptions and zero local GPU/RAM footprint from local LLM runners (e.g. Ollama). It must operate reliably within third-party free-tier quotas across Google Gemini, Groq, and OpenRouter without leaking API keys, exceeding rate limits, or failing user tasks when an upstream provider throttles or encounters outages.

## Decision
1. **Task-Specific Model Roles**:
   - Four distinct functional roles are defined:
     - `light`: Greetings, short status checks, time/date lookups (default: `gemini-2.0-flash-lite` $\to$ `openai/gpt-oss-20b` $\to$ `llama-3.1-8b-instant`).
     - `chat`: General multi-turn reasoning and planning (default: `gemini-2.0-flash` $\to$ `openai/gpt-oss-120b` $\to$ `llama-3.3-70b-versatile`).
     - `code`: Software engineering, script analysis, and code generation (default: `gemini-2.0-flash` $\to$ `openai/gpt-oss-120b` $\to$ `openrouter/free`).
     - `search`: Web result synthesis and search summarization (default: `gemini-2.0-flash-lite` $\to$ `openai/gpt-oss-20b`).
   - Role assignments and ordered fallback sequences are user-configurable via `GET /api/v1/settings/roles` and stored in SQLite.

2. **Sequential Lazy Fallback**:
   - Multi-provider queries are never dispatched in parallel (conserving quota). The primary model is queried first; fallback models are engaged sequentially only upon rate limits (HTTP 429), auth failures, or model unavailability.

3. **Live Model Discovery & Missing Model Skipping**:
   - Model endpoints are queried at startup and via `POST /api/v1/settings/models/refresh`. Deprecated or 404 models are flagged as unavailable and skipped automatically in fallback sequences.

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
   - Verbose tool outputs (search results, file contents, OCR) are pruned to 1,200 tokens.
   - Context history slides older turns out when token budgets are reached.

7. **Key Redaction & Provenance Enforcement**:
   - Provider keys and tokens are scrubbed from structlog and uvicorn access/error logs using regex filters and dynamic token registration.
   - External web, file, and OCR data are wrapped in `<untrusted_external_content>` tags, and server-side provenance (`external_untrusted`) enforces safety tiers and undo windows.

## Consequences
- **Positive**: High availability across zero-cost free tiers; graceful degradation under heavy load; zero key leaks in logs; seamless user experience via automatic retry.
- **Negative**: Temporary queuing delays when upstream free-tier quotas are entirely saturated.
