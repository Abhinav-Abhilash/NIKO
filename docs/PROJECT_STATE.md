# NIKO PROJECT STATE REPORT
**Generated:** 2026-10-02 03:45:00 UTC+05:30  
**Repository Branch:** `release/v0.3.0`  
**Latest Local Commit:** `36e6f01`  
**Execution Environment:** Windows 10/11, Python 3.12.13 (via `uv`), Node.js 20.x  

---

## SUMMARY FOR REVIEW

### System Operational Baseline
NIKO AI is an embodied, Windows-native AI desktop assistant featuring dual synchronized interfaces: a floating chibi companion pet avatar with dynamic mouth lip-sync and barge-in cut-off, and a collapsible Google Assistant-style bottom HUD card overlay. The system operates on a zero-token local neural speech engine combined with resilient multi-provider LLM orchestration, strict Human-In-The-Loop (HITL) autonomy guards, and native Windows desktop awareness tools.

### Current Implementation Status
* **Core Agent & WebSocket Hub:** **DONE** — High-concurrency bidirectional WebSocket hub with IPC fallback, topic pub/sub, audio chunk dispatch, and ping/pong keep-alives.
* **Neural Voice Engine & Lip-Sync:** **DONE** — Zero-cost, sub-300ms Microsoft Edge Neural TTS integration (`ja-JP-NanamiNeural`, +45Hz pitch, +10% rate speaking English) with in-memory Base64 audio streaming and real-time SVG mouth modulation (`0.2` to `1.0` aperture).
* **Full-Duplex Voice Barge-in:** **DONE** — Client and server-side energy gate and VAD with <100ms instant audio queue flushing and LLM stream task cancellation.
* **Desktop Tools & Sandboxed Skills:** **DONE** — Builtin tools for clipboard summarization, screen inspection/capture, window focus/management, app launch validation, file search, notes, media control, and undo shadow-copying.
* **MCP Extensibility:** **DONE** — Model Context Protocol JSON-RPC client capable of dynamically wrapping external CLI tools and sub-processes into sandboxed skills.
* **Human-In-The-Loop Autonomy Guard:** **DONE** — Tiered autonomy policy (`READ_ONLY`, `SAFE_ACTION`, `CONFIRM`, `BLOCKED`) requiring user confirmation dialogs for state-altering operations.
* **Local Memory & Local Q&A:** **DONE** — SQLite FTS5 full-text episodic memory store, semantic embeddings, and local PDF/text document parsing.

### Verified Quality Metrics
* **Backend Pytest Suite:** **218 / 218 passed** (100% success rate across 58 test files).
* **Frontend Vitest Suite:** **56 / 56 passed** (100% success rate across 16 test suites).
* **TypeScript Compiler (`tsc -p tsconfig.app.json`):** **0 errors**.
* **Python Ruff Linter (`ruff check .`):** **0 errors** (all checks clean).
* **Secret Leak Protection:** **Passed** (`test_secret_leak_guard.py` clean).
* **Memory & Performance:** Application import RSS is **80.27 MB**, cold boot duration is **2.67s**, and local SQLite database size is **252 KB**.

---

## 1. GIT AND CI

### Repository State
* **Current Working Branch:** `release/v0.3.0`
* **Tracking Remote:** `origin/release/v0.3.0` (`git@github.com:Abhinav-Abhilash/NIKO.git`)
* **Total Commits to Date:** **163 commits** (`git rev-list --count HEAD` = 163)
* **Sync Status:** Up to date with `origin/release/v0.3.0` (0 ahead, 0 behind)
* **Uncommitted Files:** 0 (Working tree completely clean)
* **Latest Local & Remote Commit Hash:** `36e6f01` (`fix(ui): derive and expose streamingContent in useChatStream for HUD overlays`)

### Recent Commit History
```text
36e6f01 fix(ui): derive and expose streamingContent in useChatStream for HUD overlays
d513a33 fix(types): enforce verbatimModuleSyntax type imports and export OrbState alias
e1309a7 test(frontend): add character and voice synchronization integration test suite
887cb2b feat(ui): propagate active speech snippet and voice state to pet companion avatar
985e470 fix(ui): synchronize pending approval state and action handlers in assistant card HUD
9637a1d feat(frontend): integrate neural audio playback, amplitude pulse lipsync, and currentSentence tracking
08e5d21 fix(frontend): align fallback API and WebSocket host port to backend port 8000
13c66fd test(backend): add voice synthesizer unit tests and clean up test fixtures and assertions
bf9840c fix(backend): mount api/v1 health prefix, seed llm orchestrator, and enhance mcp timeout resilience
38fb4ec feat(api): stream base64 neural audio chunks and barge-in signals over websocket
c90303a feat(voice): implement zero-cost Edge neural TTS with high-energy anime profile
```

### Commit Style
Strict compliance with the **Conventional Commits** specification:
* `feat(<scope>): <description>` for user-facing features and architecture modules.
* `fix(<scope>): <description>` for bug, lint, and type repairs.
* `test(<scope>): <description>` for test suites and assertion fixtures.
* `docs(<scope>): <description>` for architectural specifications and status documents.

### CI/CD Pipeline & The Pytest Hang Resolution
* **Pipeline Configuration:** [.github/workflows/ci.yml](file:///e:/NIKO%20AI/.github/workflows/ci.yml)
* **Target Branches:** `main`, `release/v0.1.0` (Note: `release/v0.3.0` will execute upon PR merge into `main`).
* **Root Cause of Earlier Pytest Hang:**
  1. AnyIO Blocking Portal teardown deadlock when WebSocket connections closed abruptly during unit test cleanup.
  2. Unbounded background asyncio worker loops in `FastAPI` lifespan (metrics collector, task scheduler, reminder worker) that kept the event loop alive indefinitely during test execution.
  3. `subprocess.wait()` lacking explicit timeout sandboxing.
* **Evidence of Fix:**
  * Commit [`48a6f9b`](https://github.com/Abhinav-Abhilash/NIKO/commit/48a6f9b) resolved the AnyIO blocking portal teardown by synchronizing WebSocket connection cleanup in `backend/app/api/v1/websocket.py` and `backend/app/core/events.py`.
  * Commit [`a6dbc77`](https://github.com/Abhinav-Abhilash/NIKO/commit/a6dbc77) guarded lifespan workers in `backend/app/main.py` by skipping long-running daemon workers when `APP_ENV=test`, and introduced strict 2.0s timeouts on subprocess teardowns in `backend/app/skills/executor.py`.
  * Real output: Full backend test suite completes deterministically in **32.67s** without hanging.

---

## 2. WHAT EXISTS VS THE SPEC

### Milestone Progress Evaluation

| Milestone | Target Specification | Status | Evidence / Paths |
|---|---|---|---|
| **M1: Core Daemon & Foundations** | SQLite FTS5 setup, Fernet secret encryption, Argon2id passwords, JWT auth, EventBus, WebSocket hub | **DONE** | [db/session.py](file:///e:/NIKO%20AI/backend/app/db/session.py), [core/security.py](file:///e:/NIKO%20AI/backend/app/core/security.py), [core/events.py](file:///e:/NIKO%20AI/backend/app/core/events.py), [api/v1/websocket.py](file:///e:/NIKO%20AI/backend/app/api/v1/websocket.py) |
| **M2: Orchestration & Streaming** | Multi-provider LLM failover, cooldown manager, sentence chunk divider, deferred queue, context budget | **DONE** | [llm/orchestrator.py](file:///e:/NIKO%20AI/backend/app/llm/orchestrator.py), [services/sentence_divider.py](file:///e:/NIKO%20AI/backend/app/services/sentence_divider.py), [llm/cooldown.py](file:///e:/NIKO%20AI/backend/app/llm/cooldown.py) |
| **M3: Skills & System Telemetry** | Skill registry, executor, provenance guard, undo window, clipboard, screenshot, window control, notes | **DONE** | [skills/registry.py](file:///e:/NIKO%20AI/backend/app/skills/registry.py), [skills/guard.py](file:///e:/NIKO%20AI/backend/app/skills/guard.py), [services/metrics_service.py](file:///e:/NIKO%20AI/backend/app/services/metrics_service.py), [skills/builtin/](file:///e:/NIKO%20AI/backend/app/skills/builtin/) |
| **M4: Full-Duplex Voice & Pet UI** | VAD, barge-in engine, Edge-TTS synthesizer, embodied chibi avatar, Google Assistant HUD card overlay | **DONE** | [services/voice_service.py](file:///e:/NIKO%20AI/backend/app/services/voice_service.py), [components/CharacterAvatar.tsx](file:///e:/NIKO%20AI/frontend/src/components/CharacterAvatar.tsx), [components/AssistantCardOverlay.tsx](file:///e:/NIKO%20AI/frontend/src/components/AssistantCardOverlay.tsx) |
| **M5: Advanced Extensibility** | Shadow-copy file snapshotting, MCP client JSON-RPC runner, local document Q&A ingestion | **DONE** | [services/shadow_copy_service.py](file:///e:/NIKO%20AI/backend/app/services/shadow_copy_service.py), [services/mcp_service.py](file:///e:/NIKO%20AI/backend/app/services/mcp_service.py), [services/document_service.py](file:///e:/NIKO%20AI/backend/app/services/document_service.py) |

### Discrepancies and Previous Misconceptions
* **Correction on ElevenLabs Cloning:** Early prompts suggested using ElevenLabs instant voice cloning with free tier keys. Free-tier accounts return `HTTP 400 paid_plan_required`. We transitioned to local, zero-token **Edge Neural TTS** (`ja-JP-NanamiNeural` with +45Hz pitch and +10% rate), eliminating cloud billing dependencies while achieving <300ms latency.
* **Correction on Health Route Mount:** Originally mounted at `/health`, which caused frontend `/api/v1/health` checks to 404. Resolved by mounting under both `/health` and `/api/v1/health` in [main.py](file:///e:/NIKO%20AI/backend/app/main.py#L232-L233).
* **Port Configuration:** Backend defaults to `8000`, while early frontend mocks defaulted to `7421`. Resolved by aligning frontend fallback to `8000`.

### Codebase Line Counts by Functional Area
* `backend/app`: **91 files, 15,219 lines** of production Python code.
* `backend/tests`: **58 files, 6,957 lines** of automated Pytest validation.
* `frontend/src`: **54 files, 10,137 lines** of React TypeScript/CSS implementation.
* `frontend/src/tests`: **17 files, 1,402 lines** of Vitest component and hook tests.
* `docs`: **18 files, 1,979 lines** of technical design documentation.
* **Total Source Size:** **238 files, 35,694 lines**.

### Directory Tree (2 Levels)
```text
E:\NIKO AI
├── backend/
│   ├── alembic/              # Database migration version scripts
│   ├── app/                  # FastAPI core application (api, core, db, llm, services, skills)
│   ├── storage/              # SQLite database and logs
│   └── tests/                # Comprehensive test suites
├── frontend/
│   ├── public/               # Static assets & icons
│   ├── src/                  # React components, hooks, services, tokens, types
│   ├── package.json          # Node dependencies and build scripts
│   └── vite.config.ts        # Vite and Vitest configuration
├── docs/                     # Architectural specifications, roadmaps, and contracts
├── scripts/                  # Environment initialization and OpenAPI export utilities
├── src-tauri/                # Native desktop shell wrapper (Rust / Cargo)
└── storage/                  # Runtime database, voice audio references, undo snapshots
```
