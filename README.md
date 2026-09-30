# NIKO - Private Personal AI Assistant

NIKO is a private, single-owner AI assistant running entirely on your local machine (`127.0.0.1`). Designed with a production-grade layered architecture, it provides autonomous system automation, real-time telemetry, and LLM orchestration with zero paid subscriptions and zero local model bloat.

---

## Key Features

- **Pure Cloud API Fallback Chain**: Tiered execution through Google Gemini (Primary free tier) $\to$ Groq (Instant fallback) $\to$ OpenRouter (Backup). Zero heavy torch/Docker dependencies.
- **Outsider Defense & Host Isolation**:
  - Bound strictly to `127.0.0.1` and `localhost` with `TrustedHostMiddleware` (blocks DNS rebinding).
  - WebSocket `/ws` Origin header validation (blocks cross-site WebSocket hijacking).
  - One-time setup token barrier (`/api/v1/auth/setup`) to claim owner account on first boot.
- **Core Orchestration & Real-Time Engine (Milestone 2)**:
  - **Bounded Async EventBus**: Internal pub/sub (`asyncio.Queue(maxsize=1000)`) routing system events with non-blocking drop-oldest backpressure.
  - **Multiplexed WebSocket Hub**: Single `/ws` connection streaming telemetry, chat chunks, and approvals with client topic subscriptions.
  - **Single-Use Cryptographic Approvals**: High-impact actions are mathematically bound to their exact arguments via SHA-256 hashes (`args_hash`) with a 30-second TTL, preventing parameter tampering or decision reuse.
  - **Audit Logging**: Comprehensive structured command logs tracking provenance, permission tiers, and execution outcomes.
  - **Hardened Session Management**: Username-keyed exponential backoff rate limiting, JWT access cookies, and refresh token rotation with token family reuse revocation.
- **Configurable Autonomy & Skill Framework (Milestone 3)**:
  - **Dynamic Skill Registry**: Extensible tool execution framework with automatic LLM tool definition generation for Gemini/Groq/OpenRouter function calling.
  - **Customizable Autonomy**: Permission tiers (`SAFE`, `CONFIRM`, `BLOCKED`) act as initial defaults, while per-skill autonomy (`ask`, `auto`, `auto+log`) is stored in SQLite and fully editable in settings without permanent lockouts.
  - **Provenance Tracking & Isolation Guard**: Identifies direct owner requests vs actions proposed downstream of untrusted external content, wrapping untrusted text in `<untrusted_external_content>` containment tags.
  - **Isolated Local PC Executor**: Subprocess execution with process-level termination on timeout, per-skill execution deadlines (`timeout_seconds`), and clean thread delegation (`run_in_thread`).
  - **Built-in System Skills**: Host date/time manipulation (`datetime`) and CPU/RAM/Disk/Battery telemetry (`system_stats`).
  - **Live Metrics Streaming & 30-Day Aggregator**: Subscriber-aware live telemetry streaming over EventBus (`sys:metrics`) at 2s intervals, dynamically throttling to 15s when browser tab is hidden, aggregating 1-minute averages to SQLite, and automatically pruning records older than 30 days.
- **Multi-Provider LLM & Streaming Chat (Milestone 4)**:
  - **Zero-Cost Model Roles**: Specializes requests into `light`, `chat`, `code`, and `search` using verified free tiers from Google Gemini, Groq, and OpenRouter (see `docs/MODELS.md`).
  - **Sequential Lazy Fallback**: Mid-turn failover without wasteful parallel burning; queries fallback models sequentially only upon HTTP 429 or provider errors.
  - **Predictive Cooldown Tracker**: Predictively pauses providers at 90% quota consumption before upstream 429 errors occur, with rolling minute and daily limit tracking.
  - **Live Discovery**: Automatically queries model list endpoints at startup and via admin refresh, skipping 404 or deprecated models.
  - **Quota-Exhaustion Deferred Queue**: When all role models are cooling down, requests enter an in-memory queue accompanied by a live frontend banner (`all providers cooling down, shortest reset in ...`) and auto-retries when cooldown ends.
  - **Streaming Chat via WebSocket**: Token streaming (`chat:chunk`) and function calls (`chat:tool_call`) over the `/ws` hub with cancellation support (`chat:cancel`).
  - **Context Sliding Window & Untrusted Wrapping**: Pins system prompt at index 0, slides older turns out, prunes tool outputs to 1,200 tokens, and wraps external untrusted content in `<untrusted_external_content>` tags.
  - **Strict Key Redaction**: Provider API keys, tokens, and secrets are scrubbed from structlog and uvicorn access/error logs.
- **Desktop Overlay Shell & Headless Wiring Architecture**:
  - **Tauri v2 Desktop Shell (`src-tauri/`)**: Frameless, transparent, always-on-top overlay with Windows 11 Acrylic / Mica effects, system tray controls, and low RAM footprint (<50MB).
  - **Global Hotkey & Auto-focus**: Summoned instantly via `Ctrl+Space`, auto-focuses the input, and auto-dismisses on `Escape` or window blur.
  - **Headless Contract (`frontend/src/hooks/`)**: Full separation of behavior from presentation via typed hooks (`useOverlay`, `useChatStream`, `useApprovals`, `useOrbState`, `useProviderStatus`) documented in `docs/UI_CONTRACT.md`.
  - **Single-Use Approvals**: 30-second countdown with keyboard shortcuts (`Enter` to approve, `Esc` to deny) and persistence settings (`session`, `always`).
  - **Flow Design Import Pipeline**: Drop design exports into `frontend/design-import/` with theme values centralized in `frontend/src/tokens.ts`.
- **Hardened SQLite Storage**: Configured with `WAL` journal mode, `PRAGMA foreign_keys = ON`, busy timeouts, and Alembic batch migrations.
- **Automated Retention**: 7-day WebP screenshot retention, 30-day downsampled system metrics, and log rotation to keep your PC storage lean.

---

## Local Setup & Quickstart (Windows)

### Prerequisites
- **Python 3.12+**
- **Node.js 18+ or 20+**
- **uv** (Astral's fast Python package manager):
  ```powershell
  # If not installed:
  pip install uv
  ```

### 1. Installation
Clone the repository and install all dependencies:
```powershell
git clone https://github.com/Abhinav-Abhilash/NIKO.git
cd NIKO
uv sync --all-extras --dev
```

### 2. Environment Configuration
Generate your secure `.env` file with generated cryptographic keys:
```powershell
uv run python scripts/init_env.py
```
This generates:
- A symmetric Fernet encryption key for encrypting provider keys in SQLite.
- A cryptographically random JWT secret key for session tokens.
- A one-time setup token required to create the first owner account.

Set your free LLM API keys in `.env` (or configure them later via the Admin UI):
```ini
INITIAL_GEMINI_API_KEY=your_gemini_api_key_here
INITIAL_GROQ_API_KEY=your_groq_api_key_here
INITIAL_OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 3. Database Migrations
Initialize the SQLite database with Alembic:
```powershell
uv run alembic upgrade head
```

### 4. Running the Backend Server
Start the local FastAPI server:
```powershell
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify server health:
```powershell
curl http://127.0.0.1:8000/health
```

---

## Testing & Quality Assurance

Run the complete test suite (78+ tests):
```powershell
uv run pytest -v
```

Run linting and strict type checking:
```powershell
uv run ruff check .
uv run mypy backend
```

---

## Architecture & Documentation

- [System Architecture Specification](docs/ARCHITECTURE.md)
- [Resource & Capacity Estimates](docs/RESOURCE_ESTIMATE.md)
- [Architectural Decision Records (ADRs)](docs/decisions/)
- [Project Changelog](CHANGELOG.md)
