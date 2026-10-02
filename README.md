# 🐾 NIKO — Embodied Desktop AI Assistant & System Orchestrator

<div align="center">

[![CI](https://github.com/Abhinav-Abhilash/NIKO/actions/workflows/ci.yml/badge.svg)](https://github.com/Abhinav-Abhilash/NIKO/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.8+-blue.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg?logo=react&logoColor=black)](https://react.dev/)
[![Tauri v2](https://img.shields.io/badge/tauri-v2-24C8DB.svg?logo=tauri&logoColor=white)](https://tauri.app/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/sqlite-WAL%20mode-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Zero Subscriptions](https://img.shields.io/badge/cost-$0%2Fmo%20(Zero%20Subs)-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <strong>A private, local-first embodied AI desktop companion and autonomous orchestrator.</strong><br>
  Lives on your screen, automates your PC, talks with sub-second voice response, and respects your privacy with mathematical security guarantees.<br>
  <em>Zero paid subscriptions. Zero local GPU/torch bloat. 100% owner-controlled.</em>
</p>

[✨ Vision](docs/VISION.md) • [🏗️ Architecture](docs/ARCHITECTURE.md) • [🤖 Model Lineup](docs/MODELS.md) • [🎨 UI Contract](docs/UI_CONTRACT.md) • [🚀 Quickstart](#-quickstart--local-setup) • [🛣️ Roadmap](docs/ROADMAP.md)

</div>

---

## 🌟 What is NIKO?

NIKO redefines personal AI. Rather than being trapped inside a browser tab or heavy terminal, **the Pet IS the AI**—an embodied desktop companion living right on your screen.

NIKO orchestrates your computer via natural language and voice, executes local skills with granular permissions, and utilizes a **pure cloud zero-cost model ladder** (Groq GPT-OSS $\to$ Google Gemini Flash Ladder $\to$ OpenRouter Free Tier) without burning a single cent on monthly subscriptions or requiring heavy local GPU models.

```
                  ┌─────────────────────────────────────────┐
                  │          🐾 EMBODIED PET & HUD          │
                  │   Transparent Tauri v2 Acrylic Window   │
                  │   (Click-to-Type • Voice • Approvals)   │
                  └────────────────────┬────────────────────┘
                                       │ WebSocket (/ws) & IPC
                  ┌────────────────────▼────────────────────┐
                  │       ⚡ NIKO FASTAPI CORE ENGINE        │
                  │  127.0.0.1 Host Isolation & Auth Guard  │
                  ├─────────────────────────────────────────┤
                  │  • Async EventBus Pub/Sub Engine        │
                  │  • Single-Use SHA-256 Approval Binding  │
                  │  • Heuristic LLM Router & Cooldowns     │
                  │  • Subprocess Execution Sandbox         │
                  └───────────┬─────────────────┬───────────┘
                              │                 │
              ┌───────────────▼──┐           ┌──▼────────────────┐
              │ 🌐 ZERO-COST LLM │           │ 🧰 SYSTEM SKILLS  │
              │  Groq GPT-OSS    │           │  Apps, Clipboard, │
              │  Gemini Flash    │           │  Volume, Display, │
              │  OpenRouter Free │           │  Notes, Schedules │
              └──────────────────┘           └───────────────────┘
```

---

## ✨ Key Features

### 🐱 The Pet IS the AI (Embodied Presence)
- **Direct Embodiment**: Click the pet to open an inline chat prompt beside it. Streamed responses appear dynamically in speech bubbles.
- **Zero Token Idle**: Blinking, breathing, walking, gaze tracking, and cute chimes run **100% locally**. Zero LLM tokens or API quotas are spent on idle presence.
- **Multi-Display Modes**: Choose between `pet-only` (default minimalist companion), `pet-overlay` (companion with floating Assistant HUD card), or `overlay-only`.
- **Customizable Persona**: Set custom names, personas, and behavioral styles directly in settings.

### 🛡️ Zero-Trust Local Security & Single-Use Approvals
- **Cryptographic Approval Binding**: High-impact system actions (launching apps, modifying files, executing commands) are mathematically bound to their exact arguments via SHA-256 hashes (`args_hash`) with a 30-second TTL countdown (`Enter` to approve, `Esc` to deny).
- **Outsider Defense**: Strict binding to `127.0.0.1` via `TrustedHostMiddleware` and WebSocket Origin validation prevents DNS rebinding and cross-site hijacking.
- **Untrusted Content Isolation**: Any text retrieved from external websites, clipboard, or documents is automatically wrapped in `<untrusted_external_content>` sandbox tags to neutralize prompt injection attacks.
- **Encrypted Local Vault**: Sensitive API keys and credentials are encrypted at rest using AES-128-CBC / Fernet with PBKDF2 HMAC-SHA256 derivation.

### ⚡ Smart Multi-Tier Zero-Cost LLM Routing
- **Heuristic Token & Role Router**:
  - **Fast (Light / Chat)**: Groq `openai/gpt-oss-20b` for short prompts $\to$ `gemini-3.5-flash-lite` $\to$ `openrouter/free`.
  - **Coder**: Groq `openai/gpt-oss-120b` $\to$ Gemini Flash ladder (`3.8-flash` $\to$ `3.7-flash` $\to$ `3.5-flash`) $\to$ OpenRouter Free.
  - **Vision / Long**: `gemini-3.5-flash-lite` $\to$ `gemini-3.8-flash`.
- **Predictive Cooldown Tracker**: Pauses providers at 90% quota consumption before upstream 429 errors trigger, with an automated quota-exhaustion deferred retry queue.
- **Deprecation Gating**: Auto-validates live model registries and skips deprecated or shut-down models with zero downtime.

### 🎙️ Sub-Second Voice Engine & Instant Barge-In
- **Real-Time Voice Activity Detection (VAD)**: Energy-based voice detection with continuous silence/speech frame tracking.
- **Instant Barge-In (Interruption)**: Speaking while NIKO is talking immediately halts TTS playback and cancels active LLM generation.
- **Neural Voice Synthesis**: Expressive edge neural text-to-speech with smart audio ducking, quiet hours, and audio unlocks.

### 🧰 Production-Grade Local Skill Engine
- **Windows System Control**: Launch apps, switch active windows, control system volume, adjust screen brightness, and capture screenshots.
- **Clipboard & Notes**: Read/write clipboard with history tracking, manage search notes, and document QA.
- **Autonomous Task Scheduling**: Schedule alarms, timers, and recurring cron-like background jobs with SQLite persistence.
- **Safety Shadow Copies & Undo**: Mutating file operations automatically create shadow backups with a 15-minute undo window.

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- **Windows 10 / 11**
- **Python 3.12+**
- **Node.js 18+ or 20+**
- **uv** (Astral's ultra-fast Python package manager)
  ```powershell
  # If uv is not installed:
  pip install uv
  ```

---

### Step 1: Clone & Install Dependencies

```powershell
# Clone the repository
git clone https://github.com/Abhinav-Abhilash/NIKO.git
cd NIKO

# Install backend dependencies in a managed virtualenv
uv sync --all-extras --dev

# Install frontend dependencies
cd frontend
npm install
cd ..
```

---

### Step 2: Initialize Security & Environment

Generate your secure `.env` file with generated cryptographic keys:
```powershell
uv run python scripts/init_env.py
```
This automatically configures:
- Symmetric Fernet master encryption key for encrypted API key storage.
- Cryptographically strong JWT secret for session tokens.
- One-time owner setup token.

Add your free-tier API keys to `.env` (or configure them later via the Settings UI):
```ini
INITIAL_GEMINI_API_KEY=your_gemini_api_key
INITIAL_GROQ_API_KEY=your_groq_api_key
INITIAL_OPENROUTER_API_KEY=your_openrouter_api_key
```

---

### Step 3: Run Database Migrations

Apply Alembic migrations to initialize the SQLite database in WAL mode:
```powershell
uv run alembic upgrade head
```

---

### Step 4: Start NIKO

In two separate terminals:

**Terminal 1 — Backend Core:**
```powershell
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend Desktop Shell:**
```powershell
cd frontend
npm run dev
```

Open your browser at `http://127.0.0.1:5173` or launch the Tauri desktop shell!

---

## 🧪 Testing & Quality Verification

NIKO enforces strict code quality, zero TypeScript errors, 100% mypy type safety, and automated secret leak protection.

```powershell
# Run the complete Python test suite (226+ tests)
uv run pytest

# Run Python linting and formatting checks
uv run ruff check .

# Run strict Python static type checking
uv run mypy backend

# Run Frontend TypeScript project reference checks
cd frontend
npx tsc -b --noEmit

# Run Frontend Vitest test suite (81+ tests)
npm test -- --run
```

---

## 📂 Repository Layout

```
NIKO/
├── backend/                  # FastAPI Core Backend Service
│   ├── app/
│   │   ├── api/v1/           # REST endpoints (auth, chat, settings, skills, storage)
│   │   ├── core/             # Security, config, encryption, exceptions
│   │   ├── db/               # SQLAlchemy models, session, migrations
│   │   ├── llm/              # Multi-provider client, router, cooldown tracker
│   │   ├── services/         # Chat, approval, voice, event bus, scheduler
│   │   └── skills/           # Extensible skill registry & built-in skills
│   └── tests/                # 226+ Comprehensive backend pytest test suite
│
├── frontend/                 # React 19 + TypeScript + Vite Frontend
│   ├── src/
│   │   ├── components/       # PetCompanion, CharacterAvatar, AssistantCard, Settings
│   │   ├── hooks/            # Headless UI contracts (useChatStream, useApprovals, etc.)
│   │   ├── services/         # WebSocket hub client, sound synthesis engine, API
│   │   └── tests/            # 81+ Vitest unit & integration test suite
│   ├── src-tauri/            # Tauri v2 Desktop Rust shell configuration
│   └── package.json
│
├── docs/                     # Comprehensive Architecture & Project Specs
│   ├── VISION.md             # Core product vision & pet embodiment philosophy
│   ├── ARCHITECTURE.md       # Layered system architecture specification
│   ├── UI_CONTRACT.md        # Headless hooks & WebSocket telemetry contract
│   ├── MODELS.md             # Free-tier model roster, verified quotas & routing rules
│   ├── ROADMAP.md            # Release milestones & feature roadmap
│   └── decisions/            # Architectural Decision Records (ADRs)
│
├── storage/                  # Local SQLite database (WAL mode) & WebP screenshots
└── pyproject.toml            # uv project configuration & dependencies
```

---

## 📜 Conventional Commits & Engineering Standards

NIKO adheres to strict engineering standards for reproducible, auditable development:

- **Atomic Commits**: One logical change per commit.
- **Conventional Commit Format**: `feat(...)`, `fix(...)`, `test(...)`, `docs(...)`, `refactor(...)`, `chore(...)`.
- **Pre-Commit Secret Scanning**: Automated protection to ensure no API keys or secrets ever touch version control (`test_secret_leak_guard.py`).
- **No Type Compromises**: Zero `any` or `@ts-ignore` in TypeScript; zero `# type: ignore` in Python without explicit verified justification.

---

## 📄 License & Credits

- Distributed under the **MIT License**. See `LICENSE` for details.
- Audio assets and sound synthesis are CC0 / MIT licensed. See [docs/CREDITS.md](docs/CREDITS.md) for full asset attribution.

<div align="center">
  <sub>Built with ❤️ by Abhinav Abhilash for private, sovereign personal computing.</sub>
</div>
