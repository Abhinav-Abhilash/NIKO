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
- **Configurable Autonomy**: Every skill defaults to `ask`, `auto`, or `auto+log` and respects a strict provenance rule (actions triggered by untrusted external data require confirmation or offer an undo window).
- **Hardened SQLite Storage**: Configured with `WAL` journal mode, `PRAGMA foreign_keys = ON`, busy timeouts, and Alembic batch migrations.
- **Automated Retention**: 7-day WebP screenshot retention, downsampled system metrics, and log rotation to keep your PC storage lean.

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

Run the complete test suite (38+ tests):
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
