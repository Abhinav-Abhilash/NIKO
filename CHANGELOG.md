# Changelog

All notable changes to the NIKO assistant project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
