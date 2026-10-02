# NIKO Desktop UI Contract & Headless Hooks Specification

This document defines the strict, unstyled contract between NIKO's core runtime logic and any visual presentation layer (such as the Flow design). The visual layer binds strictly to these headless hooks without embedding business logic or WebSocket lifecycle code.

---

## 1. `useOverlay`

Controls visibility, display modes, focus, and blur behavior of the desktop overlay window.

### Data Shape
```typescript
export type OverlayMode = 'compact' | 'expanded' | 'approval';

export interface OverlayState {
  isVisible: boolean;
  mode: OverlayMode;
  autoHideOnBlur: boolean;
  activeMonitor: string | null;
}

export interface OverlayActions {
  show: (mode?: OverlayMode) => void;
  hide: () => void;
  toggle: () => void;
  setMode: (mode: OverlayMode) => void;
  setAutoHideOnBlur: (enabled: boolean) => void;
  focusInput: () => void;
}

export type UseOverlayReturn = OverlayState & OverlayActions;
```

### Behavior & Lifecycles
- **Global Hotkey (`Ctrl+Space`)**: Toggles visibility between shown and hidden.
- **Escape Key**: Dismisses (hides) the overlay if no critical modal (such as an approval) is active.
- **Blur Auto-Hide**: When `autoHideOnBlur` is enabled, losing window focus hides the overlay (unless an active approval is pending).
- **Active Monitor**: When summoned via native shell, positions the window centered on the active display monitor.
- **Pause on Hide**: When `isVisible === false`, animations and high-frequency renders are suspended.

---

## 2. `useChatStream`

Manages conversational turns, token-by-token streaming, tool invocation events, and stream cancellation.

### Data Shape
```typescript
export interface ToolCallItem {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: 'running' | 'completed' | 'failed' | 'awaiting_approval';
  result?: unknown;
  error?: string;
}

export interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  isStreaming?: boolean;
  status: 'pending' | 'streaming' | 'completed' | 'failed' | 'cancelled';
  toolCalls?: ToolCallItem[];
  timestamp: string;
}

export interface ChatStreamState {
  messages: ChatMessageItem[];
  isStreaming: boolean;
  streamingRequestId: string | null;
  activeToolCalls: ToolCallItem[];
  error: string | null;
}

export interface ChatStreamActions {
  sendMessage: (content: string, options?: { role?: string; elevatedMode?: boolean }) => void;
  cancelStream: () => void;
  clearMessages: () => void;
}

export type UseChatStreamReturn = ChatStreamState & ChatStreamActions;
```

### Event Mappings (WebSocket)
- `chat:chunk` -> Appends text chunk to current assistant message.
- `chat:tool_call` -> Adds tool call record to current message with `status: 'running'`.
- `chat:tool_result` -> Updates tool call with `status: 'completed' | 'failed'` and result payload.
- `chat:done` -> Marks message `isStreaming: false, status: 'completed'`.
- `chat:error` -> Sets error string and marks message `status: 'failed'`.
- `chat:cancel_ack` -> Marks message `status: 'cancelled'`.

---

## 3. `useApprovals`

Manages Human-in-the-Loop (HITL) confirmation flows, countdown timers, keyboard approvals, and session permissions.

### Data Shape
```typescript
export type ApprovalPersistence = 'once' | 'session' | 'always';

export interface PendingApproval {
  approvalId: string;
  skillName: string;
  arguments: Record<string, unknown>;
  reason?: string;
  provenance: string;
  requestedAt: number;
  expiresAt: number;
  remainingSeconds: number;
}

export interface ApprovalsState {
  pendingApproval: PendingApproval | null;
  hasPendingApproval: boolean;
  remainingSeconds: number;
}

export interface ApprovalsActions {
  approve: (persistence?: ApprovalPersistence) => Promise<void>;
  deny: (reason?: string) => Promise<void>;
}

export type UseApprovalsReturn = ApprovalsState & ApprovalsActions;
```

### Behavior & Keyboard Controls
- **Auto-Popup**: If `approval:request` or `chat:approval_required` arrives while the overlay is hidden, the overlay automatically opens and receives focus.
- **30-Second Countdown**: Decrements every second. When `remainingSeconds <= 0`, triggers automatic rejection.
- **Enter Key**: When `pendingApproval !== null`, triggers `approve('once')`.
- **Escape Key**: When `pendingApproval !== null`, intercepts Escape to trigger `deny()` before the window can hide.
- **Persistence Options**:
  - `'once'`: Authorize single immediate execution.
  - `'session'`: Authorize skill execution without prompts for the duration of the current login session.
  - `'always'`: Authorize this exact skill and parameter combination permanently.

---

## 4. `useOrbState`

Single source of truth for the animated reactor core / orb state machine.

### Data Shape
```typescript
export type OrbStateType = 'idle' | 'thinking' | 'acting' | 'confirm';

export interface OrbState {
  orbState: OrbStateType;
  isIdle: boolean;
  isThinking: boolean;
  isActing: boolean;
  isConfirm: boolean;
}
```

### State Resolution Rules
1. `confirm`: Triggered whenever `useApprovals.hasPendingApproval === true`.
2. `acting`: Triggered when any tool execution is active (`activeToolCalls.length > 0`).
3. `thinking`: Triggered when an LLM stream is pending or streaming tokens (`isStreaming === true`).
4. `idle`: Resting default when no actions or streams are in-flight.

---

## 5. `useProviderStatus`

Exposes live multi-provider quota and cooldown telemetry.

### Data Shape
```typescript
export interface ProviderCooldownInfo {
  isCoolingDown: boolean;
  coolingRole: string | null;
  shortestResetSeconds: number | null;
  cooldownMessage: string | null;
}

export interface UseProviderStatusReturn extends ProviderCooldownInfo {
  clearCooldown: () => void;
}
```

### Event Mappings
- `chat:cooldown_banner` -> Activates cooldown notification with role, remaining time, and human-friendly message.

---

## 6. Flow Design Import Contract

Design files imported into `frontend/design-import/` must consume these hooks rather than custom state. Styling variables are placed in `frontend/src/tokens.ts`:
- Colors (backgrounds, surfaces, borders, text, accents)
- Typography (font families, sizes, weights, line heights)
- Spacing & Radii (padding, gap, border-radius tokens)
- Elevation & Glow (shadows, neon reactor glow vectors)

---

## 7. The Pet IS the AI & Embodied Telemetry Contract

The virtual pet companion (`PetCompanion` and `CharacterAvatar`) is **NIKO itself**—the primary embodied interface for the AI assistant. The hovering acrylic card overlay is an optional secondary HUD mode.

### Core Interaction Architecture
1. **The Pet is the Primary AI Interface**:
   - Clicking the pet avatar opens a compact inline text input directly beside it.
   - Text inputs submitted via the inline field (or voice transcripts from the mic button) stream responses directly into the pet's speech bubble above its head.
   - The microphone button toggles full-duplex voice recognition with local VAD and barge-in.
2. **Approvals Asked Through the Pet**:
   - Security-sensitive actions present human-in-the-loop (HITL) confirmation dialogs directly through the pet persona (e.g., *"Can I open Notepad?"* or *"Can I execute open_app?"*).
   - Clear **Yes (Enter)** and **No (Esc)** actions with live 30-second countdown.
   - Auto-focused and reachable (`pointer-events: auto;`) even when the desktop window is click-through.
3. **Display Modes**:
   - `pet-only` (**Default**): Embodied desktop companion with click-to-type inline input, voice mic, and speech bubble.
   - `pet-overlay`: Embodied companion and hovering acrylic card HUD displayed simultaneously, sharing identical state hooks and event feeds without duplicate logic.
   - `overlay-only`: Hovering card HUD only.
4. **Zero-Token Local Idle Telemetry**:
   - All idle animations (blinking, breathing, posture changes, eye gaze tracking) and audio effects (chimes, clicks, alerts) run strictly locally. Zero LLM tokens or API calls are consumed for idle behaviors. Model quota is spent only when the user explicitly chats or commands action.
5. **Pet Identity & Persona Settings**:
   - Pet name (default: `NIKO`) and persona are configurable in settings (`/api/v1/settings/persona`) and dynamically integrated into the system prompt.

### Real State Machine & Emotion Mapping (Zero Fake Timers)
The pet transitions only in response to genuine backend and audio pipeline events:

| Real State | Semantic State (`AssistantSemanticState`) | Posture (`CharacterPosture`) | Emotion (`CharacterEmotion`) | Telemetry Trigger / Event Topic | Payload Format |
|---|---|---|---|---|---|
| **Idle** | `ASSISTANT_IDLE` | `STANDING` | `NEUTRAL` | Default resting state; all streams idle, no active tools or cooldowns | `{ isIdle: true }` |
| **Thinking** | `ASSISTANT_THINKING` | `STANDING` | `CONFUSED` | `chat:chunk`, stream in-flight, `useChatStream.isStreaming === true`, or `orbState === 'thinking'` | `{ request_id: string, chunk?: string }` |
| **Acting** | `ASSISTANT_WORKING` | `SITTING` | `NEUTRAL` | `chat:tool_call`, `activeToolCalls.length > 0`, or `orbState === 'acting'` | `{ tool_call_id: string, name: string, arguments: Record<string, unknown> }` |
| **Waiting for Approval** | `ASSISTANT_NEEDS_PERMISSION` | `STANDING` | `SURPRISED` | `approval:request` or `chat:approval_required`, `useApprovals.hasPendingApproval === true` | `{ approval_id: string, skill_name: string, arguments: Record<string, unknown>, timeout_seconds: number, provenance: string }` |
| **Error** | `ASSISTANT_ERROR` | `STANDING` | `SAD` | `chat:error` or skill failure, `chat.error != null` | `{ message: string, code?: string }` |
| **Providers Cooling Down** | `ASSISTANT_COOLING_DOWN` | `SITTING` | `SLEEPY` | `chat:cooldown_banner`, `useProviderStatus.isCoolingDown === true` | `{ role: string, shortest_reset_seconds: number, message: string }` |
| **Speaking** | `ASSISTANT_SPEAKING` | `STANDING` | `HAPPY` | `useVoiceEngine.isSpeaking === true`; lipsync aperture driven by `audioLevel` | `{ audioLevel: number, sentence?: string }` |

### Click-Through & Unreachable-Proof Approval Specification
1. **Click-Through Desktop Layering**:
   - The desktop pet overlay root container (`#niko-pet-companion-wrapper`) is styled with `pointer-events: none;` and fixed inset bounds `0`, allowing clicks on transparent screen areas to pass through to underlying OS windows.
   - The interactive pet character (`#niko-embodied-character`) and inline input (`#pet-inline-input-wrapper`) are styled with `pointer-events: auto;`, enabling dragging, position persistence, clicking to open inline input, and microphone toggle.
2. **Approval Accessibility & Auto-Focus**:
   - When an approval request arrives, `#niko-pet-approval-card` mounts with `pointer-events: auto;` and automatically receives focus (`tabIndex={0}`).
   - An active 30-second countdown decrements live (`30s` -> `0s`).
   - Pressing **`Enter`** immediately approves execution (`approve('once')`).
   - Pressing **`Escape`** immediately cancels execution (`deny('denied_by_user')`).
   - Clickable action buttons for Approve and Deny are permanently reachable on top of any click-through desktop geometry.


