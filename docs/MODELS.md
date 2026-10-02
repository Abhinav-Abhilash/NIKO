# NIKO Model Roles & Verified Free-Tier Registry

This document records the verified model list, role assignments, and free-tier quota limits for NIKO across all supported cloud providers (**Google Gemini**, **Groq**, and **OpenRouter**).

> **Policy Enforcement**:
> - **NO Local Models / Ollama**: NIKO runs exclusively on zero-local-resource free tiers.
> - **NO Paid Models**: All models listed below are 100% free-tier eligible.
> - **Predictive Cooldown & 429 Handling**: Throttling engages predictively (at 90% quota threshold) and immediately obeys real upstream HTTP 429 response `Retry-After` headers.
> - **Live Discovery & 6-Hour Gating**: Model availability is verified via provider `list-models` endpoints at startup (no generation calls). Runtime 404/410 responses mark the target unavailable for 6 hours and emit a system event on the bus to promote the next candidate.
> - **Security & Header Auth**: Gemini API keys are passed strictly in the `x-goog-api-key` HTTP header (never exposed in query parameters or URLs). Key strings are automatically scrubbed from all logs and error traces.

---

## Final Verified Model Role Matrix

| Role | Provider | Exact Model ID | RPM | RPD | TPM | TPD | Source & Verification Date | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **`fast`** (light + chat) | **Groq** | `openai/gpt-oss-20b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-10-02) | Verified |
| **`fast`** (light + chat) | **Gemini** | `gemini-3.5-flash-lite` | 15 | 1,500 | 1,000,000 | UNVERIFIED (True quota shown in AI Studio) | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-10-02) | Verified |
| **`fast`** (backup) | **Gemini** | `gemini-flash-lite-latest` | 15 | 1,500 | 1,000,000 | UNVERIFIED (True quota shown in AI Studio) | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-10-02) | Verified (Last-resort alias) |
| **`fast`** (fallback) | **OpenRouter** | `openrouter/free` | 20 | 200 | UNVERIFIED | UNVERIFIED | [OpenRouter Free Router](https://openrouter.ai/models/openrouter/free) (Checked: 2026-10-02) | Verified (Free router) |
| **`coder`** (code) | **Groq** | `openai/gpt-oss-120b` | 30 | 1,000 | 8,000 | 200,000 | [Groq Rate Limits](https://console.groq.com/docs/rate-limits) (Checked: 2026-10-02) | Verified |
| **`coder`** (code) | **Gemini** | `gemini-3.8-flash` | 15 | 1,500 | 1,000,000 | UNVERIFIED (True quota shown in AI Studio) | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-10-02) | Verified |
| **`coder`** (backup) | **Gemini** | `gemini-flash-latest` | 15 | 1,500 | 1,000,000 | UNVERIFIED (True quota shown in AI Studio) | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-10-02) | Verified (Last-resort alias) |
| **`coder`** (fallback) | **OpenRouter** | `cohere/north-mini-code:free` | 20 | 200 | UNVERIFIED | UNVERIFIED | [OpenRouter Models](https://openrouter.ai/models) (Checked: 2026-10-02) | Verified (Free coding target) |
| **`coder`** (fallback) | **OpenRouter** | `openrouter/free` | 20 | 200 | UNVERIFIED | UNVERIFIED | [OpenRouter Free Router](https://openrouter.ai/models/openrouter/free) (Checked: 2026-10-02) | Verified (Free router) |
| **`vision_long`** (search + image/long) | **Gemini** | `gemini-3.5-flash-lite` | 15 | 1,500 | 1,000,000 | UNVERIFIED (True quota shown in AI Studio) | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-10-02) | Verified |
| **`vision_long`** (search + image/long) | **Gemini** | `gemini-3.8-flash` | 15 | 1,500 | 1,000,000 | UNVERIFIED (True quota shown in AI Studio) | [Google AI Studio Pricing](https://ai.google.dev/pricing) (Checked: 2026-10-02) | Verified |

---

## Role Configuration Defaults & Parameters

Each role implements execution constraints tailored to the task type:

1. **`fast`** (light + chat):
   - **Purpose**: Quick turn chat, greetings, status queries, date/time lookups.
   - **Max Output Tokens**: 1,024 (light) / 4,096 (chat)
   - **Reasoning Effort**: `low` (`{"thinkingConfig": {"thinkingLevel": "low"}}`)
   - **Routing Heuristic**: Short prompts (<5,000 tokens) route to Groq first; prompts over 5,000 tokens or containing image data automatically skip Groq and route to Gemini Flash-Lite.
   - **Fallback Sequence**: `groq/openai/gpt-oss-20b` $\to$ `gemini/gemini-3.5-flash-lite` $\to$ `gemini/gemini-flash-lite-latest` $\to$ `openrouter/openrouter/free`.

2. **`coder`** (code):
   - **Purpose**: Software development, debugging, code generation, script analysis.
   - **Max Output Tokens**: 8,192
   - **Reasoning Effort**: `default` / moderate (`{"thinkingConfig": {"thinkingBudget": 1024}}`)
   - **Routing Heuristic**: Short code snippets route to Groq; long code (>5,000 tokens) routes to Gemini 3.8 Flash.
   - **Fallback Sequence**: `groq/openai/gpt-oss-120b` $\to$ `gemini/gemini-3.8-flash` $\to$ `gemini/gemini-flash-latest` $\to$ `openrouter/cohere/north-mini-code:free` $\to$ `openrouter/openrouter/free`.

3. **`vision_long`** (search + vision / large context):
   - **Purpose**: Synthesizing web searches, document comprehension, screenshot/image analysis, large context files.
   - **Max Output Tokens**: 2,048
   - **Reasoning Effort**: `low`
   - **Routing Heuristic**: Skips Groq automatically when images or large inputs are detected.
   - **Fallback Sequence**: `gemini/gemini-3.5-flash-lite` $\to$ `gemini/gemini-3.8-flash` $\to$ `gemini/gemini-flash-latest`.

---

## Dynamic Discovery & Health Gating

1. **Startup Discovery**:
   - At startup, NIKO checks model availability using provider `list-models` endpoints without issuing generation requests.
   - Endpoints:
     - **Gemini**: `GET https://generativelanguage.googleapis.com/v1beta/models` (Header: `x-goog-api-key`)
     - **Groq**: `GET https://api.groq.com/openai/v1/models` (Header: `Authorization: Bearer <key>`)
     - **OpenRouter**: `GET https://openrouter.ai/api/v1/models`

2. **Runtime 404/410 Gating**:
   - If an upstream model returns HTTP 404 or 410, NIKO marks the model temporarily unavailable for 6 hours.
   - A bus event `llm:model_unavailable` is published and the next target in the fallback chain is automatically promoted.
   - The admin status API (`GET /api/v1/settings/models/status`) surfaces active and temporarily unavailable models with remaining cooldown seconds.

3. **Live Smoke Testing**:
   - Live upstream verification can be run outside CI at any time using:
     ```bash
     python scripts/smoke_models.py
     ```
