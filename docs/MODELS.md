# NIKO Model Roles & Verified Free-Tier Registry

This document records the verified model list, role assignments, and free-tier quota limits for NIKO across all supported cloud providers (**Google Gemini**, **Groq**, and **OpenRouter**).

> **Policy Enforcement**:
> - **NO Local Models / Ollama**: NIKO runs exclusively on zero-local-resource free tiers.
> - **NO Paid Models**: All models listed below are 100% free-tier eligible.
> - **True Gemini Quotas**: Verified directly from Google AI Studio rate-limit page (read 2026-10-02).
> - **Midnight Pacific Reset**: Daily request quotas reset at midnight Pacific Time (`America/Los_Angeles`).
> - **Hard-Task Reserve**: Low-RPD Flash models (20 RPD) maintain a configurable 4-request reserve strictly preserved for complex tasks, long code, and vision. Standard chat requests route through Groq and Flash-Lite (500 RPD).
> - **Flash Ladder Fallback**: For complex code or when Groq is unavailable, execution steps down the Flash ladder (`gemini-3.8-flash` $\to$ `gemini-3.7-flash` $\to$ `gemini-3.5-flash`), then falls back to `gemini-3.5-flash-lite`, followed by free OpenRouter coding models.
> - **429 Priority**: Real upstream HTTP 429 response `Retry-After` headers always override local counters and engage exponential backoff.
> - **Security & Header Auth**: Gemini keys are passed exclusively in the `x-goog-api-key` HTTP header (never exposed in URL queries).

---

## Final Verified Model Role Matrix

| Role | Provider | Exact Model ID | RPM | RPD | TPM | TPD | Source & Verification Date | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **`fast`** (light + chat) | **Groq** | `openai/gpt-oss-20b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-10-02) | Verified |
| **`fast`** (light + chat) | **Gemini** | `gemini-3.5-flash-lite` | 15 | 500 | 250,000 | 0 (Bounded by RPD) | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified |
| **`fast`** (backup) | **Gemini** | `gemini-flash-lite-latest` | 15 | 500 | 250,000 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified (Last-resort alias) |
| **`fast`** (fallback) | **OpenRouter** | `openrouter/free` | 20 | 200 | 10,000 (est.) | 0 | [OpenRouter Free Router](https://openrouter.ai/models/openrouter/free) (Checked: 2026-10-02) | Verified (Free router) |
| **`coder`** (short code) | **Groq** | `openai/gpt-oss-120b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-10-02) | Verified |
| **`coder`** (Flash ladder) | **Gemini** | `gemini-3.8-flash` | 5 | 20 | 250,000 | 0 (Separate pool) | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified (Separate 20 RPD pool) |
| **`coder`** (Flash ladder) | **Gemini** | `gemini-3.7-flash` | 5 | 20 | 250,000 | 0 (Separate pool) | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified (Separate 20 RPD pool) |
| **`coder`** (Flash ladder) | **Gemini** | `gemini-3.5-flash` | 5 | 20 | 250,000 | 0 (Separate pool) | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified (Separate 20 RPD pool) |
| **`coder`** (Flash-Lite fallback) | **Gemini** | `gemini-3.5-flash-lite` | 15 | 500 | 250,000 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified |
| **`coder`** (OpenRouter code) | **OpenRouter** | `cohere/north-mini-code:free` | 20 | 200 | 10,000 (est.) | 0 | [OpenRouter Models](https://openrouter.ai/models) (Checked: 2026-10-02) | Verified (Free coding model) |
| **`vision_long`** | **Gemini** | `gemini-3.5-flash-lite` | 15 | 500 | 250,000 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified |
| **`vision_long`** (ladder) | **Gemini** | `gemini-3.8-flash` | 5 | 20 | 250,000 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified |
| **`vision_long`** (ladder) | **Gemini** | `gemini-3.7-flash` | 5 | 20 | 250,000 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified |
| **`vision_long`** (ladder) | **Gemini** | `gemini-3.5-flash` | 5 | 20 | 250,000 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 | Verified |
| **Dead Models** | **Gemini** | `gemini-2.0-flash` / `gemini-2.0-flash-lite` | 0 | 0 | 0 | 0 | AI Studio rate-limit page, read by owner, 2026-10-02 (dead) | Shut down |

---

## Role Configuration Defaults & Parameters

1. **`fast`** (light + chat):
   - **Purpose**: Quick turn chat, greetings, status queries, date/time lookups.
   - **Max Output Tokens**: 1,024 (light) / 4,096 (chat)
   - **Reasoning Effort**: `low` (`{"thinkingConfig": {"thinkingLevel": "low"}}`)
   - **Routing Heuristic**: Short prompts (<5,000 tokens) route to Groq first; prompts over 5,000 tokens or containing image data automatically skip Groq and route to Gemini Flash-Lite. Never consumes 20-RPD full Flash models.
   - **Fallback Sequence**: `groq/openai/gpt-oss-20b` $\to$ `gemini/gemini-3.5-flash-lite` $\to$ `openrouter/openrouter/free`.

2. **`coder`** (code):
   - **Purpose**: Software development, debugging, code generation, script analysis.
   - **Max Output Tokens**: 8,192
   - **Reasoning Effort**: `default` / moderate (`{"thinkingConfig": {"thinkingBudget": 1024}}`)
   - **Routing Heuristic**: Short code snippets route to Groq; long code (>5,000 tokens) or complex tasks enter the Flash ladder.
   - **Fallback Sequence**: `groq/openai/gpt-oss-120b` $\to$ `gemini/gemini-3.8-flash` $\to$ `gemini/gemini-3.7-flash` $\to$ `gemini/gemini-3.5-flash` $\to$ `gemini/gemini-3.5-flash-lite` $\to$ `openrouter/cohere/north-mini-code:free` $\to$ `openrouter/openrouter/free`.

3. **`vision_long`** (search + vision / large context):
   - **Purpose**: Synthesizing web searches, document comprehension, screenshot/image analysis, large context files.
   - **Max Output Tokens**: 2,048
   - **Reasoning Effort**: `low`
   - **Routing Heuristic**: Starts at `gemini-3.5-flash-lite` (500 RPD), then steps into Flash ladder (`3.8` $\to$ `3.7` $\to$ `3.5`).
   - **Fallback Sequence**: `gemini/gemini-3.5-flash-lite` $\to$ `gemini/gemini-3.8-flash` $\to$ `gemini/gemini-3.7-flash` $\to$ `gemini/gemini-3.5-flash`.

---

## Daily Request Counters & Reserve Protection

- **Midnight Pacific Rollover**: Counters reset at 00:00:00 Pacific Time (`America/Los_Angeles`).
- **4-Request Hard-Task Reserve**: On models with 20 RPD (`gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.5-flash`), the last 4 requests are reserved strictly for hard tasks (long code, vision, architecture). When usage reaches 16/20, regular tasks automatically step down to `gemini-3.5-flash-lite` (500 RPD).
