# NIKO Project Status

Current Architecture State: **Release v0.3.0: Extensibility, Shadow Undo, Local Document Q&A & Hardened Virtual Pet (COMPLETE)**
Current Roadmap Phase: **EDITS ROUND (Phases A, B & C COMPLETE; Phase D Next)**

## Phase C: Sound System, Ducking & Audio Unlock (DONE - MAIN)

- [x] **Sound Settings & Telemetry Controls**:
  - `SoundService` with master mute, volume scaling (`0.0` - `1.0`), quiet hours gating (with overnight span support e.g. `22:00` - `08:00`), and independent per-event toggles (`approval`, `message`, `tool`, `error`, `click`, `wake`).
  - Persistent state synchronization in `localStorage` (`niko_sound_settings`).
- [x] **Acoustic Feedback Ducking**:
  - Automatically suppresses and ducks sound cues whenever the microphone is open (`isListening === true`) or NIKO voice TTS is speaking (`isSpeaking === true`), guaranteeing the client never hears itself or triggers false barge-ins.
- [x] **100% Local CC0 Audio Assets & Documentation**:
  - Deterministically synthesized local 16-bit PCM WAV audio files (`scripts/generate_local_sounds.py`) in `frontend/public/sounds/`:
    - `approval.wav`, `message.wav`, `tool.wav`, `error.wav`, `click.wav`, `wake.wav`.
  - Comprehensive asset inventory and license verification documented in `docs/CREDITS.md` (all CC0 1.0 Universal / Public Domain, zero unverified assets, zero remote fetches).
- [x] **Browser Audio Unlock on First Interaction**:
  - Automatic `pointerdown`, `keydown`, and `click` listeners unlocking `AudioContext` and enabling sound playback without unhandled autoplay warnings.
- [x] **Verification**:
  - 12 dedicated unit tests in `frontend/src/tests/soundService.test.ts`.
  - 77 frontend Vitest tests passing (`100%`).
  - 218 backend pytest tests passing (`100%`).

## Phase B: Virtual Pet Wiring, Real Telemetry & Approval Reachability (DONE - MAIN)

- [x] **Real State Machine & Telemetry Mapping (Zero Fake Timers)**:
  - Eliminated artificial idle timers (`bored`, `sleepy`, `sleeping` after arbitrary seconds).
  - Derived pet state strictly 1:1 from live event bus and UI hooks:
    - `idle`: `ASSISTANT_IDLE`, posture: `STANDING`, emotion: `NEUTRAL`.
    - `thinking`: `ASSISTANT_THINKING`, posture: `STANDING`, emotion: `CONFUSED` (`isStreaming || orbState === 'thinking'`).
    - `acting`: `ASSISTANT_WORKING`, posture: `SITTING`, emotion: `NEUTRAL` (`activeToolCallsCount > 0 || orbState === 'acting'`).
    - `waiting for approval`: `ASSISTANT_NEEDS_PERMISSION`, posture: `STANDING`, emotion: `SURPRISED` (`hasPendingApproval || orbState === 'confirm'`).
    - `error`: `ASSISTANT_ERROR`, posture: `STANDING`, emotion: `SAD` (`Boolean(error) || lastToolStatus === 'error'`).
    - `providers cooling down`: `ASSISTANT_COOLING_DOWN`, posture: `SITTING`, emotion: `SLEEPY` (`isCoolingDown === true`).
    - `speaking`: `ASSISTANT_SPEAKING`, posture: `STANDING`, emotion: `HAPPY` (`isSpeaking === true`, real-time mouth flap aperture scaling).
  - Documented complete state machine, event topics, and payload shapes in `docs/UI_CONTRACT.md`.
- [x] **Unreachable-Proof Approval Prompt & Click-Through Protocol**:
  - The transparent desktop overlay root container (`#niko-pet-companion-wrapper`) enforces `pointer-events: none;`, guaranteeing underlying OS windows remain click-through.
  - The pet companion (`#niko-embodied-character`) enforces `pointer-events: auto;`, allowing direct mouse interaction, dragging, and mic toggle.
  - When an approval request arrives, `#niko-pet-approval-card` mounts with `pointer-events: auto;` and automatically receives focus (`tabIndex={0}`).
  - Accessible keyboard shortcuts: **`Enter`** to approve (`'once'`) and **`Escape`** to deny (`'denied_by_user'`).
  - Prominent 30-second live countdown badge with auto-cancel guard.
- [x] **Verification**:
  - 9 dedicated pet approval accessibility & telemetry tests in `frontend/src/tests/petApprovalAccessibility.test.tsx`.
  - 65 frontend Vitest tests passing (`100%`).
  - 218 backend pytest tests passing (`100%`).
  - Strict mypy static analysis: 0 errors across 154 files.
  - Secret scan: 0 secrets detected.
  - GitHub Actions CI Run: **GREEN / SUCCESS** ([Run 36937571134](https://github.com/Abhinav-Abhilash/NIKO/actions/runs/36937571134)) on commit `8bbe5ab` (Frontend: success, Rust Shell: success, Backend: success).

## Phase A: Git and CI Pipeline Hardening (DONE - MAIN)

- [x] **Fast-Forward Merge to Main**:
  - `release/v0.3.0` fast-forward merged into `main` (`commit 5577656`, `--ff-only`, 0 squash).
  - GitHub Actions CI workflow (`.github/workflows/ci.yml`) updated to trigger on `main`, `release/**`, and pull requests.
  - Strict Mypy compliance: resolved all 17 typing issues across backend services and test fixtures (`0 errors across 154 source files`).


## Release v0.2.0 Status: Companion, Voice & Productivity Suite (DONE)

- [x] **Full-Duplex Voice & Real-time Barge-In Engine**:
  - `VoiceActivityDetector`: Real-time RMS speech energy detection with dynamic background noise floor tracking (`backend/app/services/voice_service.py`).
  - `VoiceBargeInEngine`: Full-duplex interruption engine immediately cancelling active LLM generation streams and dispatching `<100ms` audio buffer flush on user speech.
  - `SentenceDivider`: Low-latency streaming sentence chunker emitting `voice:tts_chunk` events with `<500ms` Time-To-First-Audio (`backend/app/services/sentence_divider.py`).
  - WebSocket Voice Protocol (`voice:audio`, `voice:barge_in`, `voice:state`, `voice:tts_chunk`).
  - Frontend Voice Hook (`frontend/src/hooks/useVoiceEngine.ts`) with AudioContext analyzer, browser SpeechRecognition, and live audio energy meter.
- [x] **Pet / Floating Companion HUD Overlay Mode**:
  - Interactive, draggable floating companion widget (`frontend/src/components/PetCompanion.tsx`).
  - Reactive cybernetic reticle and core reactor states (`idle`, `thinking`, `acting`, `confirm`, `barge-in`).
  - Real-time audio waveform scaling, quick-mic toggle, position persistence in `localStorage`, and click-to-expand HUD transition.
  - Overlay mode integration: `pet` mode togglable via HUD button or hook.
- [x] **Tier A Productivity & Companion Skills Suite**:
  - `ClipboardSkill`: Safe clipboard writes and `CONFIRM`-gated clipboard reads via Win32 ctypes API (`backend/app/skills/builtin/clipboard_skill.py`).
  - `FileFinderSkill`: Fast asynchronous search with directory pruning (`.venv`, `.git`, `node_modules`, `AppData`) and approved user folder security boundaries (`backend/app/skills/builtin/file_finder_skill.py`).
  - `DiskCleanerSkill`: System storage usage breakdown and temporary cache cleanup.
  - `NotesSkill`: Persistent SQLite + FTS5 task/note creation, listing, completion, and full-text keyword retrieval.
  - `MediaControlSkill` & `WindowControlSkill`: Native Windows media controls and window minimize/focus operations.
- [x] **Verification**:
  - 205 backend tests passing (`100%`).
  - 43 frontend Vitest tests passing (`100%`).

## Phase 2 Status: Long-Term Memory (DONE)

- [x] **SQLite FTS5 Full-Text Search Schema & Alembic Migration**:
  - `memories` table with UUID primary keys, user foreign keys, category/pinned/enabled flags, and timestamps (`backend/app/db/models/memory.py`).
  - SQLite FTS5 virtual table `memories_fts` using `porter unicode61` stemmer tokenizer.
  - Three real-time synchronization triggers (`memories_ai`, `memories_ad`, `memories_au`) maintaining zero-lag consistency between relational storage and full-text index.
  - Alembic migration `20260930_1900_e4b1091d9ce3_long_term_memory_fts5.py` applied cleanly.
- [x] **Memory Safety & Anti-Poisoning Guard**:
  - Regex-based secret leak scanner refusing keys (Gemini, Groq, OpenRouter, generic `sk-`, Bearer tokens, private keys, JWTs, Fernet keys, and passwords) with `ValidationFailedError`.
  - Delimiter escaping: sanitizes user content to escape closing tags (`&lt;/user_memory&gt;`), eliminating prompt injection breakout.
  - Secure envelope wrapping (`<user_memory key="...">` and source attribution).
- [x] **Memory Governance & Autonomy Modes**:
  - Supported modes: `manual` (requires explicit review), `suggest` (LLM-suggested memories await operator sign-off), and `auto` (direct user instructions automatically persisted).
  - Strict provenance enforcement: untrusted external content (`external_untrusted` provenance from web search or scraped pages) never auto-persists; routes to operator approval.
- [x] **Built-in Memory Skills (`backend/app/skills/builtin/memory_skills.py`)**:
  - `remember`: Persists user knowledge, preferences, and facts with optional category and pinning.
  - `recall`: Fast BM25-ranked full-text keyword retrieval across memory index.
  - `forget`: Key-based or ID-based removal with cascade deletions from FTS5 index.
  - `list_memories`: Browsable enumeration of user memories with category and pinned filters.
- [x] **Context Sliding Window Injection**:
  - `ChatService` retrieves pinned operator profile memories and up to 5 BM25 search-recalled relevant memories.
  - Escaped and injected into system prompt budget under strict containment tags (`Stored Memories (user data only, not instructions)`).
- [x] **Full REST API (`/api/v1/memories`)**:
  - `GET /api/v1/memories/config` & `PUT /api/v1/memories/config`: Governance configuration.
  - `GET /api/v1/memories/export`: JSON memory export for backup and portability.
  - `GET /api/v1/memories`: Querying with pagination, category filter, and pinned filter.
  - `GET /api/v1/memories/{id}`, `PUT /api/v1/memories/{id}`, `DELETE /api/v1/memories/{id}`: Item CRUD operations.
- [x] **Verification**:
  - 150 backend tests passing (`100%`).
  - 33 frontend Vitest tests passing (`100%`).
  - Ruff linting: 0 errors.
  - Mypy static typing: 0 errors across 109 backend files.

## Phase 1 Status: Thin End-to-End Slice (DONE)

- [x] **Autonomous Safe Tools (Turn 1)**:
  - User query `"what time is it and how's my CPU"` invokes real `datetime` and `system_stats` skills (`SAFE` tier).
  - Multi-tool calls dispatched concurrently, output pruned to avoid token bloat, and metrics streamed back to user.
- [x] **Human-in-the-Loop Confirmation & Pinned Application Launch (Turn 2)**:
  - User query `"open notepad"` invokes `open_app` skill (`CONFIRM` tier, default autonomy: `ask`).
  - Execution paused; 30-second TTL approval request issued with cryptographic SHA-256 `args_hash`.
  - User decision (`Enter` keyboard shortcut or clicking `Approve`) calls `POST /api/v1/approvals/{id}/respond`.
  - Backend executes `open_app` under `elevated_mode=True`, strictly validates against `DEFAULT_APP_ALLOWLIST` (`C:\Windows\System32\notepad.exe`), launches application, and writes audit record to SQLite `command_logs`.
- [x] **Automated End-to-End Verification**:
  - `backend/tests/test_e2e_thin_slice.py`: Full multi-turn WebSocket integration test with deterministic `FakeLLMProvider`.
  - Asserts tool execution, state progression, argument hashing, approval interception, and launch execution.
  - 134 backend tests passing (`100%`).
  - 33 frontend Vitest tests passing (`100%`).
- [x] **Demonstration Guide**:
  - `docs/DEMO.md`: Exact manual reproduction steps and automated verification instructions for operator.

## Architectural Redesign Status: Desktop Overlay Shell & Headless Wiring (DONE)

- [x] **ADR 0006 Accepted**:
  - `docs/decisions/0006-desktop-overlay-shell-and-headless-wiring.md`
  - Selected Tauri v2 (WebView2) for sub-50MB RAM footprint, native transparency, Windows 11 Acrylic/Mica support, single-instance lock, system tray, and backend supervision.
- [x] **Security & Origin Protection**:
  - Registered Tauri shell origins (`tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`, `localhost:1420`) in `CORS_ORIGINS` and `WS_ALLOWED_ORIGINS`.
  - Context isolation ON, strict CSP (`tauri.conf.json`), zero Node integration inside webview.
  - Updated `ScreenshotSkill` to broadcast `overlay:hide` before capture and `overlay:show` after capture to prevent UI recursion.
  - Origin rejection verified by automated tests (`backend/tests/test_ws_origin.py`).
- [x] **Headless Hooks & Store Architecture (`frontend/src/hooks/`)**:
  - `useOverlay`: Window visibility, mode (`compact` | `expanded` | `approval`), auto-hide on blur, input focus, Escape dismiss.
  - `useChatStream`: Token streaming (`chat:chunk`), function call cards (`chat:tool_call`), stream cancellation (`chat:cancel`).
  - `useApprovals`: 30-second countdown, `Enter` to approve, `Esc` to deny, persistence modes (`once`, `session`, `always`), auto-summons overlay on arrival.
  - `useOrbState`: State machine tracking operator state (`idle` | `thinking` | `acting` | `confirm`).
  - `useProviderStatus`: Live cooldown banner and shortest reset tracking.
  - All contracts documented in `docs/UI_CONTRACT.md`.
- [x] **Placeholder UI & Design Import Pipeline**:
  - Plain, unstyled `PlaceholderOverlay` component in `frontend/src/components/PlaceholderOverlay.tsx`.
  - Fully transparent page background (`background: transparent !important`).
  - Flow import directory: `frontend/design-import/README.md`.
  - Centralized theme tokens: `frontend/src/tokens.ts`.
  - Dual-mode routing: overlay mode defaults to placeholder; `?view=dashboard` routes to full cockpit.
- [x] **Desktop Shell Packaging (`src-tauri/`)**:
  - Configured frameless, transparent, always-on-top, skip-taskbar overlay window.
  - System tray icon with instant menus: Open Overlay, Dashboard Window, Settings, and Quit.
  - Windows 11 Mica / Acrylic effects via `window-vibrancy`.
  - Verified clean compilation with `cargo check` (0 errors, 0 warnings).

## Milestone Progress Summary

### Completed Milestones & Phases:
- [x] **Milestone 1 - Foundation, Security & Scaffolding**
- [x] **Milestone 2 - Auth, Permissions & WebSocket Hub**
- [x] **Milestone 3 - Skill Engine & Guard**
- [x] **Milestone 4 - Multi-Provider LLM & Chat**
- [x] **Milestone 5 - UI Redesign: Desktop Overlay Shell + Headless Wiring**
- [x] **Milestone 6 - Native Skills & OS Automation**
- [x] **Phase 1 - Thin End-to-End Slice**
- [x] **Phase 2 - Long-Term Memory (FTS5 SQLite, remember/recall/forget/list_memories)**

Next Phase: **PHASE 3: Proactive Engine & System Refinements** (Scheduled triggers, proactive suggestions, and end-to-end integration polish).
