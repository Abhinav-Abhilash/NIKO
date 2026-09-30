# NIKO Project Status

Current Milestone: **Milestone 5 - Autonomous AI Cockpit (Frontend Complete & Hardened)**

## Milestone Progress Summary

### Completed Milestones:
- [x] **Milestone 1 - Foundation, Security & Scaffolding**
  - TrustedHostMiddleware (127.0.0.1, localhost)
  - One-time setup token barrier (`SETUP_TOKEN`)
  - SQLite WAL mode, foreign keys ON, Alembic batch mode
  - Strict secret scanning & zero secrets policy
- [x] **Milestone 2 - Auth, Permissions & WebSocket Hub**
  - Argon2id password authentication with rotating `httpOnly` session cookies
  - WebSocket hub multiplexer with strict localhost origin validation
  - Cryptographic HMAC audit log trail
- [x] **Milestone 3 - Skill Engine & Guard**
  - LocalExecutor with process timeouts and Windows worker safety
  - SkillGuard with provenance tracking and `<untrusted_external_content>` wrapping
  - Strict BLOCKED tier enforcement across all modes
- [x] **Milestone 4 - Multi-Provider LLM & Chat**
  - Model Roles: `Chat`, `Fast`, `Reasoning`
  - Cloud Providers: Google Gemini, Groq Cloud, OpenRouter (Ollama removed)
  - Predictive cooldown tracker & dynamic live model discovery
  - Quota-exhaustion deferred queue with live cooldown banner
  - Multi-provider LLM orchestrator with sliding context & key redaction
- [x] **Milestone 5 - UI Frontend Cockpit & Telemetry (Complete & Verified)**
  - Google Stitch AI Cockpit dark & light design system integration
  - React 19 + TypeScript + Tailwind CSS (`frontend/`)
  - Real-time WebSocket streaming client with 15s heartbeats & exponential reconnect
  - Signature Animated Concentric SVG Reactor Core (`CockpitCore.tsx`)
  - Streaming Chat Viewport with tool execution cards & untrusted provenance boundaries
  - Human-in-the-Loop (HITL) approval modal with 30s auto-cancel
  - Persisted draggable dashboard grid with provider matrix
  - Reactive toast notification system with 5-second undo window
  - Global Command Palette (`⌘K`) and Keyboard Shortcuts Reference (`?` / `⌘/`)
  - Operator Login & Setup Modal with zero `localStorage` secrets
  - OpenAPI generated TypeScript client (`openapi-typescript` + `scripts/export_openapi.py`)
  - 100% Vitest unit tests passing (12/12 tests) and Vite production build clean

- [x] **Milestone 6 - Remaining Native Skills & OS Automation**
  - Built-in OS Skills: `OpenAppSkill` (with command injection guard), `RemindersSkill`, `ScreenshotSkill`, `VolumeBrightnessSkill`, `WebSearchSkill`, `YouTubePlaySkill`, `DateTimeSkill`, `SystemStatsSkill`
  - Async Reminders Service (`ReminderService`) with background loop and WebSocket `/ws` broadcast
  - Reminders REST API (`/api/v1/reminders`) with full CRUD support
  - 100% test coverage across OS skills, security constraints, and background scheduling (132/132 backend tests passing)

Next Milestone: **Milestone 7 - Production Readiness, Packaging & Self-Hosting**
