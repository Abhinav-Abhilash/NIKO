# Changelog

All notable changes to the NIKO assistant project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.0] - Milestone 4: Multi-Provider LLM Orchestration, Streaming Chat & Quota Resilience

### Added
- **Multi-Provider LLM Architecture & Fallback Engine**:
  - Implemented base provider interface and standardized message/tool types (`LLMMessage`, `NormalizedToolCall`, `StreamChunk`, `LLMResponse`).
  - Native provider adapters for Google Gemini (SSE streaming, tool calling), Groq (LPU streaming, delta tool assembly), and OpenRouter (free fallback models).
  - Four distinct task roles (`light`, `chat`, `code`, `search`) configured with verified free-tier models and fallback sequences in `docs/MODELS.md`.
  - Sequential lazy fallback: models are queried sequentially without wasteful parallel burns.
  - Tool output pruning: trims verbose tool outputs to 1,200 tokens using head/tail truncation.
- **Predictive Cooldown Tracker & Dynamic Discovery**:
  - `PredictiveCooldownTracker` tracks rolling minute and daily requests/tokens, engaging cooldown predictively at 90% quota thresholds.
  - Upstream HTTP 429 and `Retry-After` header extraction with exponential backoff.
  - `ModelDiscoveryService` dynamically probes provider model endpoints at startup and via `POST /api/v1/settings/models/refresh`, automatically skipping 404/deprecated models.
- **Model Roles & Settings Persistence**:
  - `SettingsRepository` for storing encrypted provider keys and ordered role models in SQLite.
  - REST endpoints: `GET /api/v1/settings/roles`, `PUT /api/v1/settings/roles`, `POST /api/v1/settings/models/refresh`, `GET /api/v1/settings/models/status`.
- **Security & Key Redaction**:
  - Comprehensive logging redaction processor and uvicorn logging filter preventing provider API keys (Gemini, Groq, OpenRouter, bearer tokens) from appearing in logs.
  - Dynamic sensitive token registration for configured keys and secrets.
- **ChatService & Conversation Management**:
  - `ConversationRepository` managing persistent conversations, messages, and tool call audit states.
  - Token-budget sliding context window pinning the system prompt at index 0.
  - Server-side provenance resolution setting `external_untrusted` when web/file/OCR data enters context.
  - Automatic wrapping of untrusted data inside `<untrusted_external_content>` containment delimiters.
  - Clean, direct system prompt instructing the model that untrusted content is raw data, free of refusals, topic limits, or hedging.
  - Integrated tool dispatch through `SkillService` and `SkillGuard`, enforcing human approvals (`CONFIRMATION_REQUIRED`) and toast undo windows.
- **WebSocket Chat Streaming & Cancellation**:
  - Real-time chat streaming over `/ws` emitting `chat:chunk` text tokens and `chat:tool_call` events.
  - Client cancellation support (`chat:cancel`) cleanly terminating active execution tasks.
- **Quota-Exhaustion Deferred Queue & Cooldown Banner**:
  - In-memory `DeferredQueue` holding requests when all providers for a role are cooling down.
  - Cooldown banner events (`all providers cooling down, shortest reset in ...`) broadcast over EventBus and WebSocket.
  - Automatic retry worker re-executing deferred requests and clearing the banner when cooldown expires.
- **Architecture Documentation & Decision Records**:
  - Created ADR 0005 (`docs/decisions/0005-model-roles-and-fallback.md`).
  - Added project tracking documentation (`docs/STATUS.md`).

---

## [0.3.0] - Milestone 3: Skill Framework, System Telemetry & Live Metrics

### Added
- **Extensible Skill Framework**:
  - Base abstractions (`BaseSkill`, `SkillManifest`, `SkillResult`, `SkillContext`, `SkillExecutor`).
  - `SkillRegistry` providing capability discovery, duplicate guard, and LLM tool definition export (`get_tool_definitions`).
  - High-level `SkillService` orchestrating execution, persistent SQLite settings, human approval triggers, and audit logging.
  - REST endpoints: `GET /api/v1/skills`, `PATCH /api/v1/skills/{name}`, `POST /api/v1/skills/{name}/execute`.
- **Per-Skill Autonomy & Provenance Guard**:
  - Permission tiers (`SAFE`, `CONFIRM`, `BLOCKED`) act as initial defaults, fully customizable via database settings (`ask`, `auto`, `auto+log`).
  - `SkillGuard` provenance tracking distinguishing direct owner prompts from downstream actions following untrusted external data.
  - Untrusted content isolation via `<untrusted_external_content>` tags.
  - Non-blocking undo window support (`requires_toast_undo=True`) for low-friction monitoring.
- **Isolated Local PC Executor (`LocalExecutor`)**:
  - Per-skill execution timeout barriers (`timeout_seconds`) with clean error recovery and millisecond execution timing.
  - Async subprocess execution with process group kill on timeout.
  - Thread-pool delegation for synchronous blocking OS/psutil operations (`run_in_thread`).
  - Full interface abstraction behind `SkillExecutor` for future remote agent execution.
- **Built-in System Skills**:
  - `DateTimeSkill`: host date, time, day of week, timezone, and custom strftime formatting.
  - `SystemStatsSkill`: CPU (cores and per-core utilization), RAM (total, used, percent), Disk partitions, and battery diagnostics.
- **Live Telemetry & Historical Metrics Aggregator**:
  - `MetricsService` polling host performance and streaming `sys:metrics` on the EventBus.
  - Subscriber-aware telemetry: pauses polling completely when zero subscribers are active on the bus.
  - Adaptive cadence: 2-second streaming during active interaction, dropping to 15-second background sampling when browser tab is hidden.
  - 1-minute aggregation persisting average telemetry to SQLite with automatic 30-day retention pruning.
  - REST endpoints: `GET /api/v1/metrics/current`, `GET /api/v1/metrics/history`, `POST /api/v1/metrics/visibility`.
- **Testing & Verification**:
  - 29 new tests covering manifest validation, registry schema export, provenance guard rules, executor timeouts, metrics throttling, and API routes.
  - Total test suite expanded to 78 passing unit and integration tests.

---

## [0.2.0] - Milestone 2: Core Orchestration Engine, Auth & Real-Time Bus

### Added
- **Asynchronous Bounded EventBus**:
  - In-process pub/sub system backed by `asyncio.Queue(maxsize=1000)`.
  - Non-blocking drop-oldest overflow strategy to ensure real-time latency under bursts without memory leaks.
  - Granular topic subscriptions (`sys:metrics`, `chat:stream`, `approval:request`, `reminder:trigger`) and global subscriptions.
- **Multiplexed WebSocket Hub (`/ws`)**:
  - Bidirectional multiplexing streaming live events from the EventBus to connected frontends.
  - Strict Origin header verification preventing Cross-Site WebSocket Hijacking (CSWSH).
  - Multi-method authentication supporting cookies, URL query tokens, and post-connection `auth` messages.
  - Client-controlled dynamic topic subscription filtering.
- **Single-Use Cryptographic Human-in-the-Loop Approvals**:
  - `ApprovalRepository` and `ApprovalService` implementing a strict 30-second TTL on all high-impact actions.
  - Cryptographic argument hash verification: execution arguments are compared against original user-displayed parameters using constant-time digest checks.
  - State machine validation preventing expired approval execution or decision reuse.
  - REST endpoints: `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{id}`, `POST /api/v1/approvals/{id}/respond`.
- **Hardened Authentication & Session Management**:
  - Username-keyed exponential backoff rate limiting preventing brute-force password guessing on localhost without self-lockout.
  - Refresh token rotation with token family reuse detection (revokes all active sessions upon replay attack detection).
  - Secure httpOnly session cookie storage with SameSite protections.
  - Dependency injection guards (`get_current_user`, `get_current_owner`).
  - Endpoints: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
- **Structured Audit Logging**:
  - `AuditRepository` and `AuditService` recording all tool and system executions.
  - Provenance tracking (direct vs. untrusted external input), permission tier classification (`SAFE`, `CONFIRM`, `BLOCKED`), arguments, and IP attribution.
- **Automated Test Isolation**:
  - Autouse fixture in test suite automatically truncating all SQLite tables between tests.
  - Total test count expanded to 38 unit and integration tests across crypto, origin validation, auth rotation, approvals, event bus, and WebSocket hub.

---

## [0.1.0] - Milestone 1: Scaffolding, Core Security, Database & Health Check

### Added
- **Foundational Architecture**: Layered structure (`api -> services -> repositories -> db`) with strict typing (`mypy strict`) and modern linting (`ruff`).
- **Network Isolation Middleware**:
  - `TrustedHostMiddleware` enforcing `127.0.0.1` and `localhost` to prevent DNS rebinding.
  - WebSocket `/ws` Origin validation to reject foreign web pages (WS code `1008`).
- **Initial Boot Barrier**: One-time cryptographically secure `SETUP_TOKEN` required to register the initial owner account; endpoint permanently disables once an owner exists.
- **Cryptographic Security**:
  - Argon2id password hashing for owner credentials.
  - Fernet symmetric encryption for external API keys stored in SQLite.
  - Deterministic SHA-256 argument hashing (`args_hash`) for single-use approval binding.
- **Database & Storage Foundation**:
  - SQLite with WAL journal mode, busy timeouts, and `foreign_keys=ON`.
  - Alembic migrations running in batch mode (`render_as_batch=True`).
  - Indexed tables: `users`, `sessions`, `conversations`, `messages`, `tool_calls`, `approvals`, `command_logs`, `skills`, `llm_providers`, `settings`, `system_metrics`, `reminders`, `storage_reports`.
- **Executable Validation**: Path pinning for `open_app` against a canonical allowlist, preventing directory traversal and script wrapper launches (`.cmd`, `.bat`, `.ps1`).
- **Secret Scanning & Leak Guard**: Pre-commit `detect-secrets` baseline and automated test ensuring zero secrets exist in tracked files.
- **Observability**: Standardized `APIErrorResponse` envelope, request ID tracking (`X-Request-ID`), structured logging via `structlog`, and `/health` diagnostic endpoint.
- **Windows CI**: GitHub Actions workflow running on `windows-latest` with dynamic runtime test secret generation.
