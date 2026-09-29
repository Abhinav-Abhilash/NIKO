# NIKO Model Roles & Verified Free-Tier Registry

This document records the verified model list, role assignments, and free-tier quota limits for NIKO across all supported cloud providers (**Google Gemini**, **Groq**, and **OpenRouter**).

> **Policy Enforcement**:
> - **NO Local Models / Ollama**: NIKO runs exclusively on zero-local-resource free tiers.
> - **NO Paid Models**: All models listed below are 100% free-tier eligible.
> - **Predictive Cooldown**: Throttling engages before reaching quotas (at 90% threshold) using local request/token tracking and upstream 429 response headers.
> - **Live Discovery**: Models are validated against provider endpoints at startup and via manual admin refresh. Missing or 404 models are skipped with warnings.

---

## Final Verified Model Role Matrix

| Role | Provider | Exact Model ID | RPM | RPD | TPM | TPD | Source & Verification Date | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **`light`** | **Gemini** | `gemini-2.0-flash-lite` | 15 | 1,500 | 1,000,000 | Uncapped* | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-09-29) | Verified |
| **`light`** | **Groq** | `openai/gpt-oss-20b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-09-29) | Verified |
| **`light`** | **Groq (alt)** | `llama-3.1-8b-instant` | 30 | 14,400 | 6,000 | 500,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-09-29) | Verified |
| **`chat`** | **Gemini** | `gemini-2.0-flash` | 15 | 1,500 | 1,000,000 | Uncapped* | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-09-29) | Verified |
| **`chat`** | **Groq** | `openai/gpt-oss-120b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-09-29) | Verified |
| **`chat`** | **Groq (alt)** | `llama-3.3-70b-versatile` | 30 | 1,000 | 12,000 | 100,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-09-29) | Verified |
| **`code`** | **Gemini** | `gemini-2.0-flash` | 15 | 1,500 | 1,000,000 | Uncapped* | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-09-29) | Verified |
| **`code`** | **Groq** | `openai/gpt-oss-120b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-09-29) | Verified |
| **`code`** | **OpenRouter** | `openrouter/free` | 20 | 200 | *Unverified* | *Unverified* | [OpenRouter Free Router](https://openrouter.ai/models/openrouter/free) (Checked: 2026-09-29) | Partial (TPM/TPD unverified upstream) |
| **`code`** | **OpenRouter (alt)** | `qwen/qwen-2.5-coder-32b-instruct:free` | 20 | 200 | *Unverified* | *Unverified* | [OpenRouter Models](https://openrouter.ai/models) (Checked: 2026-09-29) | Partial (TPM/TPD unverified upstream) |
| **`search`** | **Gemini** | `gemini-2.0-flash-lite` | 15 | 1,500 | 1,000,000 | Uncapped* | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-09-29) | Verified |
| **`search`** | **Groq** | `openai/gpt-oss-20b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-09-29) | Verified |

*\* Note: Gemini free-tier daily token limits are not published as a static number by Google and are bounded by the 1,500 RPD and 1M TPM quotas per Google Cloud project.*

---

## Role Configuration Defaults & Parameters

Each role defines execution constraints tailored to the task category:

1. **`light`**:
   - **Purpose**: Greetings, simple direct queries, quick date/time lookups, status checks.
   - **Max Output Tokens**: 1,024
   - **Reasoning Effort**: `low`
   - **Tool Schema Filtering**: Only attach matching read-only/lookup tool schemas.
   - **Fallback Sequence**: `gemini/gemini-2.0-flash-lite` $\to$ `groq/openai/gpt-oss-20b` $\to$ `groq/llama-3.1-8b-instant`.

2. **`chat`**:
   - **Purpose**: Multi-turn conversation, reasoning, planning, general queries.
   - **Max Output Tokens**: 4,096
   - **Reasoning Effort**: `default`
   - **Fallback Sequence**: `gemini/gemini-2.0-flash` $\to$ `groq/openai/gpt-oss-120b` $\to$ `groq/llama-3.3-70b-versatile`.

3. **`code`**:
   - **Purpose**: Software engineering, debugging, code generation, script analysis.
   - **Max Output Tokens**: 8,192
   - **Reasoning Effort**: `default`
   - **Fallback Sequence**: `gemini/gemini-2.0-flash` $\to$ `groq/openai/gpt-oss-120b` $\to$ `openrouter/openrouter/free`.

4. **`search`**:
   - **Purpose**: Synthesizing web search results, URL scraping, knowledge retrieval over pruned inputs.
   - **Max Output Tokens**: 2,048
   - **Reasoning Effort**: `low`
   - **Fallback Sequence**: `gemini/gemini-2.0-flash-lite` $\to$ `groq/openai/gpt-oss-20b`.

---

## Dynamic Discovery & Fallback Behavior

1. **Startup Discovery**:
   - On server startup, NIKO attempts to list available models via each configured provider's list endpoint:
     - **Gemini**: `GET https://generativelanguage.googleapis.com/v1beta/models`
     - **Groq**: `GET https://api.groq.com/openai/v1/models`
     - **OpenRouter**: `GET https://openrouter.ai/api/v1/models` (filtered to `:free` and tool support)
   - If an endpoint returns 404, 401, or cannot reach a model, NIKO logs a warning and marks that model as unavailable without halting backend boot.

2. **Admin Refresh**:
   - The admin can trigger `POST /api/v1/settings/models/refresh` to re-query all endpoints and refresh the active model availability cache.

3. **Predictive Cooldown**:
   - Token and request tallies are recorded per-provider per-minute and per-day in SQLite and in-memory rate limiters.
   - When 90% of RPM, RPD, TPM, or TPD is consumed, the model initiates cooldown *predictively* before an upstream HTTP 429 error occurs.
   - Real upstream `429 Too Many Requests` responses and `Retry-After` headers immediately engage a cooldown backoff window.
   - If all models for a role enter cooldown, requests enter the deferred queue accompanied by an active frontend cooldown banner.
