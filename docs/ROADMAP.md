# NIKO Product & Technical Roadmap (v0.2.0+)

> **Mission:** Transform NIKO from a security-hardened desktop assistant into a high-agency, personal AI companion for Windows 11 that commands local and frontier AI models with extreme responsiveness, uncompromising safety, and sub-500ms voice interactions.

---

### Roadmap Overview & Release Phases

```
+-----------------------------------------------------------------------------------+
| RELEASE v0.1.0 (CURRENT BASELINE - COMPLETED)                                    |
| - Security Hardening (LOLBin defense, HMAC provenance, setup barrier)             |
| - Desktop Overlay HUD (Acrylic glassmorphic theme & reactor core orb)             |
| - Task Queue & Scheduled Hooks Engine (Cron evaluator, proactive telemetry)       |
| - Storage Maintenance & Online Backups (SQLite WAL backup, 7-day log/pic janitor) |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| RELEASE v0.2.0: COMPANION & PRODUCTIVITY SKILLS (Quick Wins)                      |
| 1. Tier A Productivity Skills (Clipboard, Notes & Tasks, File Finder, Media/Win)  |
| 2. Full-Duplex Voice & Interruption Engine (Silero VAD, Streaming ASR/TTS)        |
| 3. Pet / Floating Companion Overlay Mode                                          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| RELEASE v0.3.0: EXTENSIBILITY & ADVANCED AGENT AGENCY                              |
| 1. Sandboxed MCP Client Support (Model Context Protocol with Approval Gates)      |
| 2. Reversible Action Shadow-Copy & Extended Undo Engine                           |
| 3. Local Document Q&A (SQLite FTS5 + Optional Embeddings RAG)                     |
+-----------------------------------------------------------------------------------+
```

---

### Phase v0.2.0: Companion & Productivity Skills

#### Item 2.1: Tier A Companion & Productivity Skill Suite
- **Why:** Delivers immediate, everyday utility ("summarize clipboard", "search my docs", "pause music", "create task") that turns NIKO into a daily companion.
- **How NIKO Does It Better:**
  - *Clipboard:* Read operations require explicit `CONFIRM` gate (since clipboards contain passwords), while write operations are `SAFE`.
  - *File Finder:* Scoped strictly to user-approved directory allowlists (no unmonitored disk traversal).
  - *Media & Window Control:* Uses native Windows Win32 / Media Key APIs without fragile PyAutoGUI coordinate clicks.
- **Acceptance Criteria:**
  - Clipboard skill supports `read_clipboard` and `write_clipboard`.
  - Local Notes & To-dos stored in SQLite with full FTS5 search capabilities.
  - File Finder searches by filename or content inside approved folders and opens file in default app.
  - Media Control handles Play, Pause, Next, Prev, and Volume adjustments.
  - Window Control focuses, minimizes, or lists active window titles.
- **Risks & Mitigation:** Clipboard leaks sensitive data -> Strict `CONFIRM` approval modal for read operations.
- **Rough Effort:** 2 Days (Low Effort, High Value).
- **Dependencies:** NIKO `SkillService`, `ApprovalService`, SQLite database.

#### Item 2.2: Full-Duplex Voice Interaction & Barge-In Engine
- **Why:** Conversational natural voice interactions without needing to click or type.
- **How NIKO Does It Better:**
  - Unlike Mark-LV's hard-muting echo guard (which prevents voice interruption), NIKO uses ONNX Silero VAD for full-duplex speech detection.
  - When user speaks while NIKO is talking, the server immediately aborts the active LLM stream and flushes audio buffers in <100ms.
- **Acceptance Criteria:**
  - Audio worklet streams PCM input over WebSocket to backend.
  - Streaming sentence-boundary TTS (`sentence_divider`) begins audio playback within 500ms TTFA.
  - Speech during TTS triggers instant server cancellation (`asyncio.Task.cancel()`) and client audio queue flush.
- **Risks & Mitigation:** VAD noise false positives -> Adaptive background noise floor calibration and audio energy gating.
- **Rough Effort:** 4 Days.
- **Dependencies:** WebSockets, `sentence_divider`, Silero VAD.

#### Item 2.3: Pet / Floating Companion HUD Mode
- **Why:** Gives NIKO a persistent visual presence as a sleek desktop companion that sits unobtrusively on screen.
- **How NIKO Does It Better:**
  - Built with Tauri v2 transparent window capabilities with minimal CPU/GPU overhead (unlike heavy 3D mesh engines that consume constant GPU).
  - Smooth reactive animations reacting to `orb.orbState` (Idle, Thinking, Acting, Confirming).
- **Acceptance Criteria:**
  - Compact floating pet widget mode togglable via hotkey or tray context menu.
  - Click-through transparency support and drag-to-reposition persistence.
- **Risks & Mitigation:** High CPU usage -> CSS/SVG hardware-accelerated animations instead of heavy 3D renders.
- **Rough Effort:** 2 Days.
- **Dependencies:** Tauri v2 window capabilities, `tokens.ts`.

---

### Phase v0.3.0: Extensibility & Advanced Agency

#### Item 3.1: Sandboxed MCP Client Support (Model Context Protocol)
- **Why:** Unlocks hundreds of community integrations (GitHub, Slack, PostgreSQL, Brave Search) via standard MCP servers.
- **How NIKO Does It Better:**
  - Unlike Open-LLM-VTuber (which grants unmonitored execution to MCP tools), every MCP tool call in NIKO MUST pass through NIKO's `ApprovalService` confirmation gate.
  - Enforces per-MCP-server scope permissions (folder boundaries, API domain allowlists).
- **Acceptance Criteria:**
  - Configuration format for registering MCP stdio/SSE servers (`storage/mcp_servers.json`).
  - Tools parsed dynamically into OpenAI JSON schema formats.
  - High-risk MCP tools trigger NIKO approval modal showing resolved tool name, parameters, and risk level.
- **Risks & Mitigation:** Malicious third-party MCP servers -> Strict approval gate + execution timeout sandbox (15s hard limit).
- **Rough Effort:** 4 Days.
- **Dependencies:** `mcp` SDK, `ApprovalService`, `SkillService`.

#### Item 3.2: Reversible Action Shadow-Copy & Extended Undo Engine
- **Why:** Allows users to confidently grant NIKO file automation rights knowing any accidental deletion or modification can be undone.
- **How NIKO Does It Better:**
  - Before modifying or deleting any file, NIKO takes an automatic temporary shadow copy in `storage/undo_staging/`.
  - Extends NIKO's existing 5-second undo window into a multi-step undo history log.
- **Acceptance Criteria:**
  - File skills (`delete_file`, `overwrite_file`, `clean_temp`) create a shadow snapshot before execution.
  - Saying "undo that" restores original files and rolls back system state.
  - Automated janitor purges undo staging files older than 24 hours.
- **Risks & Mitigation:** High disk storage use -> Shadow copies capped at 500MB total size.
- **Rough Effort:** 3 Days.
- **Dependencies:** `JanitorService`, `BackupService`, `ApprovalService`.

#### Item 3.3: Local Document Q&A (SQLite FTS5 + Optional Embeddings RAG)
- **Why:** Enables asking questions over local PDFs, notes, and code repositories.
- **How NIKO Does It Better:**
  - Zero mandatory cloud vector DB dependencies. Starts with local SQLite FTS5 full-text indexing for zero latency and zero disk overhead.
  - Optional local sentence-transformer embeddings with size-capped vector index.
- **Acceptance Criteria:**
  - PDF & markdown text extraction and chunking pipeline.
  - FTS5 keyword and semantic vector search API.
  - Retained document context cited cleanly in chat responses.
- **Risks & Mitigation:** Token limit exhaustion from long documents -> Automatic context window compression and chunk trimming.
- **Rough Effort:** 5 Days.
- **Dependencies:** SQLite FTS5, `MemoryService`.
