# NIKO System Specification

**Version:** 1.2.0  
**Target Platform:** Windows 10/11 (Single-Owner Localhost)  
**Security Classification:** Private Local Assistant (Outsider-Protected, User-Autonomous, Zero Secrets in Codebase)

---

## 1. Core Architecture & Philosophy

NIKO is a private, local-first autonomous AI desktop assistant designed with uncompromised reasoning, multi-provider sequential fallback, and robust security boundaries.

### Guiding Principles:
- **Zero Refusals / Moralizing:** System prompts contain no preachiness, refusal rules, or synthetic topic limits.
- **Configurable Autonomy:** All permission tiers and guardrails are defaults that the owner can configure.
- **Strict BLOCKED Tier Enforcement:** Any skill placed in the `BLOCKED` tier is strictly non-runnable and cannot be executed under any mode.
- **Provenance-Based Guarding:** Prompts originating from the direct owner execute immediately according to the user's chosen autonomy. Actions proposed downstream of untrusted external sources (web pages, downloaded files, screen OCR) require human confirmation or execute with a non-blocking toast and 5-second undo window.
- **Untrusted Tagging:** Untrusted external observations are strictly demarcated within `<untrusted_external_content>` delimiters and treated as data.

---

## 2. Multi-Provider LLM Orchestration & Model Roles

NIKO uses a multi-tier, sequential fallback architecture across high-speed cloud providers.

> [!NOTE]
> Local Ollama has been removed from active routing to eliminate heavy local VRAM memory constraints and dependency friction. All LLM operations route sequentially through cloud APIs.

### Active Providers & Supported Models:
1. **Google Gemini:** `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `gemini-flash-lite-latest`, `gemini-flash-latest` (Streaming via SSE, function calling, header auth via `x-goog-api-key`).
2. **Groq Cloud:** `openai/gpt-oss-20b`, `openai/gpt-oss-120b` (High-speed LPU inference with token streaming).
3. **OpenRouter:** `openrouter/free`, `cohere/north-mini-code:free` (Free-tier coding and general fallback).

### Model Roles & Fallback Chains:
- **`fast` Role (Quick chat, light queries, short classification):**
  1. `groq/openai/gpt-oss-20b` (for short prompts <5,000 tokens)
  2. `gemini/gemini-3.5-flash-lite`
  3. `gemini/gemini-flash-lite-latest` (backup)
  4. `openrouter/openrouter/free`
- **`coder` Role (Code generation, debugging, script analysis):**
  1. `groq/openai/gpt-oss-120b` (for short code snippets <5,000 tokens)
  2. `gemini/gemini-3.8-flash` (for long code)
  3. `gemini/gemini-flash-latest` (backup)
  4. `openrouter/cohere/north-mini-code:free`
  5. `openrouter/openrouter/free`
- **`vision_long` Role (Search synthesis, OCR, image inputs, long context):**
  1. `gemini/gemini-3.5-flash-lite`
  2. `gemini/gemini-3.8-flash`
  3. `gemini/gemini-flash-latest`

### Quota Avoidance & Deferred Queue:
- **Routing Heuristics:** Prompts over ~5,000 estimated tokens or containing image data automatically bypass Groq and route directly to Gemini.
- **Predictive Cooldown Tracker:** Automatically cools down a provider/model at 90% quota consumption or upon upstream HTTP 429 responses with `Retry-After`.
- **Runtime 404/410 Gating:** Runtime 404/410 marks the target unavailable for 6 hours, emits a bus event, and promotes the next model in sequence.
- **Deferred Chat Queue:** If all providers for a role are simultaneously cooling down, requests are buffered in a deferred queue and automatically retried when the shortest reset timer expires, while broadcasting a live cooldown banner to the UI.

---

## 3. Cryptographic Audit Trail & HMAC Integrity

Every skill execution, authorization event, and system state transition is recorded in an immutable audit ledger with HMAC-SHA256 integrity verification:
- Each audit log entry is cryptographically hashed with the server-side secret.
- The UI verifies the HMAC signature to detect and flag any database tampering or unauthorized row modifications.

---

## 4. Authentication & Operator Sessions

- **Argon2 Password Hashing:** User passwords hashed using Argon2id.
- **httpOnly Session Cookies:** JWT access token (`niko_access_token`) and rotating refresh token (`niko_refresh_token`) stored strictly in `httpOnly`, `SameSite=Lax` cookies. Zero tokens stored in `localStorage`.
- **First-Boot Setup Token:** On initial deployment, a one-time 32-byte `SETUP_TOKEN` printed to server logs is required to initialize the owner account. Once initialized, setup is permanently locked.

---

## 5. UI Cockpit & Design System

Built with React 19, TypeScript, and Tailwind CSS based on the Google Stitch AI Cockpit specification:
- **Cyberpunk Dark & Light Theme:** `#0c0e11` surface base, `#ffb020` amber gold primary container, `#4ae176` neon emerald telemetry accents.
- **Animated SVG Reactor Core:** Concentric spinning rings visualizing thinking and streaming states.
- **Real-Time WebSocket Hub:** `/ws` hub with auto-reconnect, 15s heartbeats, streaming chunks, tool call cards, and approval modals.
- **Modular Persisted Dashboard:** Draggable, persisted telemetry widgets (CPU, RAM, IPC latency, provider matrix).
- **Toast Notifications & Undo Window:** Reactive toasts with a 5-second undo window for safe untrusted actions.
- **Global Command Palette:** `⌘K` launcher with keyboard navigation.
