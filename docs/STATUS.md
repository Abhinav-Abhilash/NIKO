# NIKO Project Status

Current Architecture State: **Desktop Overlay Shell & Headless Wiring Architecture (COMPLETE)**
Current Roadmap Phase: **PHASE 1: Thin End-to-End Slice (Ready to Execute)**

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
- [x] **Automated Test Coverage**:
  - 133 backend unit and integration tests passing (`100%`).
  - 33 frontend Vitest unit tests passing across all 9 test suites (`100%`).
  - Frontend production build clean (`tsc -b && vite build` passing in ~3.6s).

## Milestone Progress Summary

### Completed Milestones:
- [x] **Milestone 1 - Foundation, Security & Scaffolding**
- [x] **Milestone 2 - Auth, Permissions & WebSocket Hub**
- [x] **Milestone 3 - Skill Engine & Guard**
- [x] **Milestone 4 - Multi-Provider LLM & Chat**
- [x] **Milestone 5 - UI Redesign: Desktop Overlay Shell + Headless Wiring**
- [x] **Milestone 6 - Native Skills & OS Automation**

Next Phase: **PHASE 1: Thin End-to-End Slice** (proving "what time is it and how's my CPU" and "open notepad" approval flow end-to-end with automated fake LLM test and `docs/DEMO.md`).
