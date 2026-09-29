# Changelog

All notable changes to the NIKO assistant project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
