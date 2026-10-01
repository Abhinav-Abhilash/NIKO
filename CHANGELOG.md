# Changelog

All notable changes to the NIKO assistant project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - Release v0.3.0: Extensibility, Shadow Undo & Local Document Q&A

### Added
- **Sandboxed MCP Client Engine (Model Context Protocol)**:
  - Asynchronous JSON-RPC 2.0 stdio/SSE client protocol engine (`backend/app/services/mcp_service.py`).
  - Dynamic tool schema translation mapping MCP `inputSchema` into OpenAI-compatible `SkillManifest` parameter definitions.
  - Strict security tiering with `CONFIRM` gate / `ApprovalService` approval modals and execution timeout sandboxing (15s hard limit).
  - MCP Server configuration management (`storage/mcp_servers.json`) with auto-start and dynamic skill registration.
  - Full REST API (`/api/v1/mcp/servers`, `/api/v1/mcp/tools`) for registering, starting, stopping, and enumerating MCP servers.
- **Reversible Action Shadow-Copy & Extended Undo Engine**:
  - `ShadowCopyService`: Automatic pre-action shadow staging in `storage/undo_staging/<snapshot_id>/` before file deletions or destructive mutations (`backend/app/services/shadow_copy_service.py`).
  - `UndoSkill` (`backend/app/skills/builtin/undo_skill.py`): Reversible action rollback with "undo that" natural language invocation.
  - Multi-step snapshot manifest tracking original paths, SHA-256 integrity hashes, and file metadata.
  - Automatic expiration janitor capping staging storage at 500MB and purging snapshots older than 24 hours.
  - REST API (`/api/v1/undo/snapshots`, `/api/v1/undo/revert`).
- **Local Document Q&A & Ingestion (SQLite FTS5 + RAG)**:
  - Document extraction pipeline (`backend/app/services/document_service.py`) for PDF, Markdown, text, and code files.
  - Sliding-window token/character chunking with 200-character overlap.
  - Relational database schema with SQLite FTS5 virtual table `document_chunks_fts` using Porter stemmer tokenizer and auto-sync triggers.
  - `DocumentSearchSkill` (`backend/app/skills/builtin/document_search_skill.py`): BM25-ranked full-text keyword retrieval across indexed user documents.
  - REST API (`/api/v1/documents`, `/api/v1/documents/ingest`, `/api/v1/documents/search`).
- **Verification**:
  - 216 backend tests passing (`100%`).
  - 43 frontend Vitest tests passing (`100%`).

## [0.2.0] - Release v0.2.0: Companion, Voice & Productivity Suite

### Added
- **Full-Duplex Voice & Real-time Barge-In Engine**:
  - `VoiceActivityDetector`: Real-time RMS speech energy detection with dynamic background noise floor tracking (`backend/app/services/voice_service.py`).
  - `VoiceBargeInEngine`: Full-duplex interruption engine immediately cancelling active LLM generation streams and dispatching `<100ms` audio buffer flush on user speech.
  - `SentenceDivider`: Low-latency streaming sentence chunker emitting `voice:tts_chunk` events with `<500ms` Time-To-First-Audio (`backend/app/services/sentence_divider.py`).
  - WebSocket Voice Protocol (`voice:audio`, `voice:barge_in`, `voice:state`, `voice:tts_chunk`).
  - Frontend Voice Hook (`frontend/src/hooks/useVoiceEngine.ts`) with AudioContext analyzer, browser SpeechRecognition, and live audio energy meter.
- **Pet / Floating Companion HUD Overlay Mode**:
  - Interactive, draggable floating companion widget (`frontend/src/components/PetCompanion.tsx`).
  - Reactive cybernetic reticle and core reactor states (`idle`, `thinking`, `acting`, `confirm`, `barge-in`).
  - Real-time audio waveform scaling, quick-mic toggle, position persistence in `localStorage`, and click-to-expand HUD transition.
  - Overlay mode integration: `pet` mode togglable via HUD button or hook.
- **Tier A Productivity & Companion Skills Suite**:
  - `ClipboardSkill`: Safe clipboard writes and `CONFIRM`-gated clipboard reads via Win32 ctypes API (`backend/app/skills/builtin/clipboard_skill.py`).
  - `FileFinderSkill`: Fast asynchronous search with directory pruning (`.venv`, `.git`, `node_modules`, `AppData`) and approved user folder security boundaries (`backend/app/skills/builtin/file_finder_skill.py`).
  - `DiskCleanerSkill`: System storage usage breakdown and temporary cache cleanup.
  - `NotesSkill`: Persistent SQLite + FTS5 task/note creation, listing, completion, and full-text keyword retrieval.
  - `MediaControlSkill` & `WindowControlSkill`: Native Windows media controls and window minimize/focus operations.
- **Verification**:
  - 205 backend tests passing (`100%`).
  - 43 frontend Vitest tests passing (`100%`).

## [0.8.0] - Phase 2: Long-Term Memory (SQLite FTS5 & Governance)

### Added
- **SQLite FTS5 Full-Text Search Schema & Alembic Migration**:
  - Relational `memories` table with UUID keys, user mapping, categories, pinned flags, and timestamps (`backend/app/db/models/memory.py`).
  - SQLite FTS5 virtual table (`memories_fts`) using Porter stemmer tokenizer and auto-sync triggers (`memories_ai`, `memories_ad`, `memories_au`).
  - Alembic migration `20260930_1900_e4b1091d9ce3_long_term_memory_fts5.py`.
- **Memory Safety & Anti-Poisoning Guard (`backend/app/services/memory_safety.py`)**:
  - Regex secret leak scanner refusing keys (Gemini, Groq, OpenRouter, generic `sk-`, Bearer tokens, private keys, JWTs, Fernet keys, passwords) with `ValidationFailedError`.
  - Delimiter escaping: sanitizes user memories to escape closing tags (`&lt;/user_memory&gt;`), eliminating prompt injection breakout.
  - Secure envelope wrapping (`<user_memory key="...">` and provenance metadata).
- **Memory Governance & Autonomy Modes**:
  - Supported modes: `manual` (requires explicit review), `suggest` (LLM-suggested memories await operator sign-off), and `auto` (direct user instructions automatically persisted).
  - Strict provenance enforcement: untrusted external content (`external_untrusted` provenance from web search or scraped pages) never auto-persists; routes to operator approval.
- **Built-in Memory Skills (`backend/app/skills/builtin/memory_skills.py`)**:
  - `RememberSkill`: Persists user knowledge, preferences, and facts with optional category and pinning.
  - `RecallSkill`: Fast BM25-ranked full-text keyword retrieval across memory index.
  - `ForgetSkill`: Key-based or ID-based removal with cascade deletions from FTS5 index.
  - `ListMemoriesSkill`: Browsable enumeration of user memories with category and pinned filters.
- **Context Sliding Window Injection**:
  - `ChatService` retrieves pinned operator profile memories and up to 5 BM25 search-recalled relevant memories.
  - Escaped and injected into system prompt budget under strict containment tags (`Stored Memories (user data only, not instructions)`).
- **Full REST API (`/api/v1/memories`)**:
  - `GET /api/v1/memories/config` & `PUT /api/v1/memories/config`: Governance configuration.
  - `GET /api/v1/memories/export`: JSON memory export for backup and portability.
  - `GET /api/v1/memories`: Querying with pagination, category filter, and pinned filter.
  - `GET /api/v1/memories/{id}`, `PUT /api/v1/memories/{id}`, `DELETE /api/v1/memories/{id}`: Item CRUD operations.
- **Verification**:
  - 150 backend tests passing (`100%`).
  - 33 frontend Vitest tests passing (`100%`).
  - Ruff linting: 0 errors.
  - Mypy static typing: 0 errors across 109 backend files.

## [0.7.0] - Desktop Overlay Shell & Headless Wiring Architecture

### Added
- **Desktop Overlay Shell (Tauri v2)**:
  - Frameless, transparent, always-on-top overlay window with Windows 11 Acrylic / Mica compositing (`src-tauri/`).
  - System tray icon with instant menus: Open Overlay, Dashboard Window, Settings, and Quit.
  - Global hotkey toggle (`Ctrl+Space`) with conflict resolution.
  - Automatic backend child process supervision: checks `127.0.0.1:8000`, spawns local uvicorn instance on launch, and cleans up on exit.
  - Single-instance lock focusing the existing overlay window if re-launched.
  - Fully transparent page background (`background: transparent !important`).
- **Headless Hooks & Store Layer (`frontend/src/hooks/`)**:
  - `useOverlay`: Controls window visibility, mode (`compact` | `expanded` | `approval`), auto-hide on blur, input focus, and Escape dismiss.
  - `useChatStream`: Manages token streaming (`chat:chunk`), function call execution cards (`chat:tool_call`), and stream aborts (`chat:cancel`).
  - `useApprovals`: Implements 30s auto-canceling countdown, `Enter` to approve, `Esc` to deny, and persistence modes (`once`, `session`, `always`). Auto-summons overlay on arrival.
  - `useOrbState`: Reactive state machine tracking operator states (`idle` | `thinking` | `acting` | `confirm`).
  - `useProviderStatus`: Real-time multi-provider cooldown banner and shortest reset monitoring.
- **Unstyled Placeholder UI**:
  - `PlaceholderOverlay`: Minimal, unstyled DOM component proving complete end-to-end functionality without hardcoded visual styles or colors.
  - Visual design import pipeline: `frontend/design-import/` and theme token definitions in `frontend/src/tokens.ts`.
- **Security & Origin Protection**:
  - Registered Tauri shell origins (`tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`, `localhost:1420`) in `CORS_ORIGINS` and `WS_ALLOWED_ORIGINS`.
  - Updated `ScreenshotSkill` to broadcast `overlay:hide` before frame capture and `overlay:show` after capture to avoid UI recursion.
  - Full automated test suite for hooks, approval keyboard navigation, and overlay lifecycle (33 frontend tests passing).

## [0.6.0] - Milestone 6: Native Skills & OS Automation

### Added
- **Built-in OS Native Skills**:
  - `OpenAppSkill`: Application launching with command injection validation, shell character escaping (`&|;><$\` etc.), and path traversal blocks.
  - `RemindersSkill`: Local natural reminder creation and querying via `ReminderService`.
  - `ScreenshotSkill`: Screen capture utility saving timestamped frames to local storage.
  - `VolumeBrightnessSkill`: Windows system audio and display brightness controls via PowerShell subprocess wrappers.
  - `WebSearchSkill`: External web query retrieval with untrusted provenance tagging and 1200-token result pruning.
  - `YouTubePlaySkill`: Safe browser media launcher opening YouTube queries in default browser.
  - `DateTimeSkill` and `SystemStatsSkill`: Local system time, CPU, memory, and disk telemetry.
- **Background Reminders Service & REST API**:
  - `ReminderService` async background loop polling for pending reminders and dispatching `reminder:triggered` events over `EventBus` and `/ws`.
  - Full REST API (`/api/v1/reminders`) for listing, creating, snoozing, and canceling reminders.
- **Skill Engine Integration**:
  - Registered all native skills in `SkillService` with tiering, timeouts, and undo window support.
  - Comprehensive unit test suite with 100% pass rate (132/132 backend tests).

## [0.5.0] - Milestone 5: UI Frontend Cockpit & Real-time Telemetry

### Added
- **React 19 Frontend Cockpit**:
  - High-performance dashboard built with React 19, TypeScript, and Tailwind CSS matching Google Stitch specifications.
  - Signature Animated Concentric SVG Reactor Core (`CockpitCore.tsx`) visualizing streaming and thinking states.
  - Real-time WebSocket streaming client with 15s heartbeats, exponential backoff reconnects, and message dispatch.
  - Human-in-the-Loop (HITL) approval modal with 30s auto-cancel timeout.
  - Reactive toast notification system with 5-second undo window for safe untrusted action reversion.
  - Global Command Palette (`⌘K`) and Keyboard Shortcuts Reference (`?` / `⌘/`).
  - Persisted draggable telemetry dashboard with provider matrix and system resource gauges.
  - Fully typed OpenAPI client auto-generated with `openapi-typescript`.

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
