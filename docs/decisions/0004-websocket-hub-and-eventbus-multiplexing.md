# Decision Record: 0004 - WebSocket Hub & EventBus Multiplexing

## Context
NIKO requires real-time bidirectional communication between the localhost backend and frontend for:
1. Streaming LLM token generation chunks (`chat:stream`).
2. High-frequency telemetry updates (`sys:metrics`).
3. Human-in-the-loop tool execution approval notifications (`approval:request` and `approval:resolved`).
4. Timed reminder notifications (`reminder:trigger`).

Because NIKO runs as a local agent, exposed ports must resist Cross-Site WebSocket Hijacking (CSWSH) and unauthorized cross-origin connections while maintaining minimal latency and bounded memory consumption.

## Decision
1. **Bounded AsyncIO EventBus**:
   - Internal pub/sub architecture backed by an asynchronous bounded queue (`asyncio.Queue(maxsize=1000)`).
   - Topic-based and global subscriptions.
   - Non-blocking drops for stale high-frequency events when a consumer's queue is full, preserving real-time latency without exhausting RAM.
2. **WebSocket Hub (`/ws`) Multiplexer**:
   - Strict `Origin` header validation against `WS_ALLOWED_ORIGINS` (`http://127.0.0.1:5173`, `http://localhost:5173`), terminating unauthorized web origins with `1008 Policy Violation`.
   - Dual authentication: accepts JWT credentials via `niko_access_token` cookie, query parameter `?token=...`, or client `{"type": "auth", "token": "..."}` frame.
   - Dynamic client-side topic filtering (`{"type": "subscribe", "topics": [...]}`) allowing the UI to receive only relevant streams.
   - Clean shutdown with `contextlib.suppress(asyncio.CancelledError)` to eliminate connection hanging.

## Consequences
- Fast, decoupled pub/sub throughout the backend architecture.
- Web browsers running hostile external websites cannot connect to or read events from the local assistant.
- Minimal CPU and RAM footprint during idle and streaming periods.
