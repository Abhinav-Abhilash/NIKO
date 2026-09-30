# ADR 0006: Desktop Overlay Shell (Tauri v2) & Headless Wiring Architecture

## Context
NIKO requires an always-available desktop overlay that can be summoned instantly via a global hotkey (default `Ctrl+Space`), present notifications/confirmations on the active monitor, and dismiss cleanly on `Escape` or blur. To ensure maximum responsiveness with minimal memory footprint, the UI layer must remain lightweight (<60MB RAM footprint idle) while the visual styling is designed independently in Flow.

The redesign requires:
1. A frameless, transparent, always-on-top desktop overlay shell with system tray integration and single-instance enforcement.
2. Complete separation of behavior and state from presentation: headless hooks/stores (`useChatStream`, `useApprovals`, `useOrbState`, `useProviderStatus`, `useOverlay`) that expose contract-defined primitives without embedded styling, animations, or colors.
3. Strict security boundary preservation: CORS and WebSocket origin verification for the shell origin, strict CSP, no Node.js integration inside the webview context, and preservation of HMAC-bound approval workflows.

## Decision

### 1. Framework Selection: Tauri v2 over Electron
We select **Tauri v2 (with WebView2 on Windows)** rather than Electron.
- **Memory Footprint**: Tauri utilizes the system-installed Evergreen Microsoft Edge WebView2 control. Idle memory footprint is ~30–50MB compared to Electron's typical baseline of 150–300MB.
- **Transparency & Windows 11 Compositing**: Tauri v2 natively supports transparent windows (`transparent: true`, `decorations: false`, `always_on_top: true`, `skip_taskbar: true`) and integrates directly with Windows DWM compositions (Acrylic/Mica backdrop effects via `window_vibrancy`).
- **Global Shortcuts & Tray**: Tauri v2 provides native OS global shortcuts (`@tauri-apps/plugin-global-shortcut`) with conflict resolution reporting, and native tray menus (`TrayIconBuilder`).
- **Lifecycle Management**: The overlay window is hidden (`window.hide()`) rather than destroyed when dismissed. While hidden, all React animation loops and rendering work are suspended to keep background CPU at ~0%.
- **Backend Process Supervision**: Tauri starts the local Python FastAPI backend (`127.0.0.1:8000`) as a managed child sidecar if it is not already running, and terminates it gracefully upon tray `Quit`.

### 2. Headless State & Behavior Architecture
All UI functionality is encapsulated into unstyled, headless React hooks and stores:
- `useChatStream`: Manages WebSocket chat streaming, token accumulation, tool call dispatches, and cancellation.
- `useApprovals`: Implements the 30-second countdown timer, `Enter` to approve, `Esc` to deny, and persistence choices ("allow for this session", "always allow this exact action"). Automatically signals the overlay shell to show and take focus if an approval arrives while hidden.
- `useOrbState`: State machine tracking operator state (`idle` | `thinking` | `acting` | `confirm`).
- `useProviderStatus`: Tracks multi-provider availability, cooldown banners, and shortest reset timeouts.
- `useOverlay`: Coordinates window visibility, current monitor positioning, input auto-focus, and auto-hide on blur settings.

The complete interface contract and TypeScript signatures are documented in `docs/UI_CONTRACT.md`.

### 3. Visual Decoupling & Flow Import Pipeline
- The runtime web view root (`index.html`, `body`) is styled with `background: transparent`.
- The active view defaults to an unstyled, plain placeholder UI (HTML text input, raw message list, approval buttons).
- Design exports from Flow are placed in `frontend/design-import/`. When the operator commands "apply design", the placeholder is substituted with the imported components wired directly to the headless hooks, referencing styling tokens defined centrally in `frontend/src/tokens.ts`.

### 4. Security & Isolation Controls
- **Origin Validation**: The shell's native origin (`tauri://localhost` and `http://tauri.localhost`) is explicitly added to backend `CORS_ORIGINS` and `WS_ALLOWED_ORIGINS`.
- **WebSocket Protection**: Origin checks remain strictly enforced. External/unauthorized browser origins continue to receive `1008 Policy Violation` closures.
- **Context Isolation**: No direct Node integration or unbounded OS access from the webview. Native OS interactions (clipboard, global shortcuts) are accessed exclusively via vetted Tauri plugin IPC permissions with strict CSP.
- **Screenshot Shielding**: Built-in screenshot skills notify the overlay shell to temporarily hide before frame capture and restore immediately after, preventing UI recursion.

## Status
Accepted.
