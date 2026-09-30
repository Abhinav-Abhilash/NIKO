# NIKO Project Status

Current Architecture State: **Phase 1: Thin End-to-End Slice (COMPLETE)**
Current Roadmap Phase: **PHASE 2: Long-Term Memory (FTS5 SQLite, remember/recall/forget/list_memories)**

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

Next Phase: **PHASE 2: Long-Term Memory** (FTS5 SQLite, skills: remember/recall/forget/list_memories, anti-poisoning, secret scanner refusal, 5 memories + profile injection).
