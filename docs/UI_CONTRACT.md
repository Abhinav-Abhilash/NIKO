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
