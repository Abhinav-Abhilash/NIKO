# ADR 0001: Sequential LLM Fallback and Token Conservation

## Status
Accepted

## Context
NIKO requires zero paid subscriptions and must operate under free-tier quotas from third-party LLM providers (Google Gemini, Groq, OpenRouter). Parallel multi-model dispatching wastes limited daily requests and tokens. Local model runners (e.g. Ollama) would consume gigabytes of disk and significant memory/compute on the host machine.

## Decision
1. Eliminate local model requirements and execute exclusively via free-tier cloud APIs: Gemini $\to$ Groq $\to$ OpenRouter.
2. The fallback chain is strictly **sequential and lazy**: Groq is queried only when Gemini returns a rate-limit (HTTP 429), quota exhaustion, or timeout error. OpenRouter is queried only when Groq fails.
3. Chat history uses a sliding context window, and verbose tool outputs (e.g. web search results, process lists) are truncated to a maximum of 1,200 tokens before re-injecting into the model context.
4. When all providers are exhausted, NIKO enters a temporary cooldown state and offers an in-memory deferred request queue.

## Consequences
- **Positive**: Zero local disk bloat from weights; maximum reliability across free providers; minimizes token burn.
- **Negative**: Requires Internet connectivity for LLM reasoning.
