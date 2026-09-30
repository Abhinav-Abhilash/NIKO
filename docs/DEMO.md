# NIKO Phase 1: Thin End-to-End Slice Demo Guide

This document describes how to execute and verify the **Phase 1 Thin End-to-End Slice** of NIKO, proving the complete multi-turn interaction cycle across the desktop overlay, real-time WebSocket hub, tool execution engine, and human-in-the-loop approval workflow.

---

## 1. Overview of the Flow

1. **Turn 1 (Autonomous Safe Tools)**:
   - User queries: `"what time is it and how's my CPU"`
   - NIKO invokes the `datetime` and `system_stats` tools autonomously (`SAFE` tier).
   - Real-time CPU, RAM, and system clock metrics are retrieved and streamed back to the user.
2. **Turn 2 (Human-in-the-Loop Confirmation)**:
   - User commands: `"open notepad"`
   - NIKO identifies the `open_app` tool call (`CONFIRM` tier, autonomy policy: `ask`).
   - Execution pauses and raises a cryptographic approval request with a 30-second TTL countdown.
   - The user presses **Enter** (or clicks **Approve**).
   - NIKO verifies the single-use cryptographic `args_hash`, validates the pinned binary path (`C:\Windows\System32\notepad.exe`), and launches Notepad on the host.

---

## 2. Automated End-to-End Verification

To run the automated thin slice test using a deterministic mock LLM provider:

```powershell
uv run pytest backend/tests/test_e2e_thin_slice.py -v
```

This automated test validates:
- Multi-turn conversation persistence across WebSockets.
- Dispatch and execution of `datetime` and `system_stats` builtin skills.
- Interception of `open_app` tool calls requiring user authorization.
- Verification that no processes are spawned prior to confirmation.
- Resolution via `POST /api/v1/approvals/{id}/respond` and verified process launch of `notepad.exe`.

---

## 3. Manual Reproduction Steps

### Step 1: Initialize Environment & Backend

1. In your terminal, ensure dependencies and environment configuration are initialized:
   ```powershell
   uv sync --all-extras --dev
   python scripts/init_env.py
   ```

2. Start the FastAPI backend server:
   ```powershell
   uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```

### Step 2: Launch the Frontend / Desktop Shell

You can run the unstyled placeholder overlay either via the browser or the native Tauri v2 desktop shell.

#### Option A: Web Browser Dev Server
```powershell
npm run dev --prefix frontend
```
Navigate to `http://localhost:5173/` in your browser.

#### Option B: Native Desktop Overlay Shell (Tauri v2)
```powershell
npm run tauri:dev
```
- The frameless transparent overlay will start in the background.
- Toggle visibility using the global shortcut: **`Ctrl+Space`** (or click the tray icon).

---

### Step 3: Execute Turn 1 (Time & System Stats)

1. Focus the input bar (`#niko-chat-input`).
2. Type:
   ```text
   what time is it and how's my CPU
   ```
3. Press **Enter** (or click **Send**).
4. **Expected Outcome**:
   - The Orb state changes to `tool_executing` then `streaming`.
   - Tool execution badges appear:
     - `[Tool: datetime (completed)]`
     - `[Tool: system_stats (completed)]`
   - NIKO streams a natural response reporting the current time and live CPU/RAM utilization.

---

### Step 4: Execute Turn 2 (Open Notepad Approval)

1. In the same conversation, type:
   ```text
   open notepad
   ```
2. Press **Enter** (or click **Send**).
3. **Expected Outcome**:
   - The input disables and an amber confirmation card appears:
     ```text
     CONFIRMATION REQUIRED (30s)
     Skill: open_app
     Arguments: {"app_name": "notepad"}
     ```
   - The Orb state changes to `awaiting_approval`.
   - A 30-second countdown timer decrements.
   - Notepad has **not** yet opened.

---

### Step 5: Approve the Action

1. With the approval card active, press **Enter** (or click the **Approve (Enter)** button).
2. **Expected Outcome**:
   - The approval card dismisses.
   - NIKO authorizes execution in `elevated_mode`.
   - **`notepad.exe` immediately opens on your Windows desktop**.
   - An audit trail record is logged to the SQLite database (`command_logs` table) with status `success` and permission tier `CONFIRM`.

---

## 4. Security & Safety Properties Verified

- **Pinned Path Validation**: `open_app` resolves strictly against `DEFAULT_APP_ALLOWLIST` (or user-defined settings allowlist). Arbitrary script wrappers (`.bat`, `.cmd`, `.ps1`) are blocked.
- **Cryptographic Binding**: The approval decision carries the canonical SHA-256 hash of the arguments displayed to the user (`args_hash`), preventing argument tampering.
- **Single-Use & TTL Enforcement**: Approvals expire after 30 seconds and cannot be replayed or re-decided once resolved.
