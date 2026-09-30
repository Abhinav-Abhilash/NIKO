# NIKO Project Status

Current Roadmap Phase: **PHASE 0: Milestone 4 Completion & CI Hardening (COMPLETE)**
Next Roadmap Phase: **PHASE 1: Thin End-to-End Slice**

## Roadmap Execution Status

### Phase 0: Milestone 4 Completion & CI Hardening (DONE)
- [x] **Key Redaction in Logs**:
  - Implementation: `backend/app/core/logging.py`
  - Automated Tests: `backend/tests/test_log_scrubbing.py` (5 tests passing)
- [x] **ChatService**:
  - Implementation: `backend/app/services/chat_service.py`
  - Automated Tests: `backend/tests/test_chat_service.py` (7 tests passing)
- [x] **Chat Streaming over WebSockets**:
  - Implementation: `backend/app/api/v1/websocket.py`
  - Automated Tests: `backend/tests/test_ws_chat_streaming.py` (4 tests passing)
- [x] **Deferred Quota Queue**:
  - Implementation: `backend/app/llm/deferred_queue.py`
  - Automated Tests: `backend/tests/test_deferred_queue.py` (3 tests passing)
- [x] **CI Pytest Teardown & Hang Fixes**:
  - Isolated test lifespan from background network discovery and metrics worker loops (`APP_ENV == "test"` guards in `backend/app/main.py`)
  - Subprocess timeouts hardened with non-blocking join on Windows in `backend/app/skills/executor.py`
  - EventBus lock contention eliminated during generator cancellation in `backend/app/core/events.py`
  - WebSocket chat streaming DB commit ordered strictly ahead of `chat:done` emission, preventing task cancellation and SQLite connection deadlocks in `backend/app/api/v1/websocket.py`
  - Added `pytest-timeout==2.4.0` with `timeout = 15` in `pyproject.toml`
  - Converted `.secrets.baseline` to UTF-8
  - Fixed Starlette TestClient blocking portal lifecycle across all WebSocket tests (`test_ws_chat_streaming.py`, `test_ws_hub.py`, `test_ws_origin.py`)
  - Result: 132 backend unit/integration tests passing in ~18 seconds, 12 frontend tests passing in ~12 seconds.

## Milestone Progress Summary

### Completed Milestones:
- [x] **Milestone 1 - Foundation, Security & Scaffolding**
- [x] **Milestone 2 - Auth, Permissions & WebSocket Hub**
- [x] **Milestone 3 - Skill Engine & Guard**
- [x] **Milestone 4 - Multi-Provider LLM & Chat**
- [x] **Milestone 5 - UI Frontend Cockpit & Telemetry**
- [x] **Milestone 6 - Remaining Native Skills & OS Automation**
  - Built-in OS Skills: `OpenAppSkill` (with command injection guard), `RemindersSkill`, `ScreenshotSkill`, `VolumeBrightnessSkill`, `WebSearchSkill`, `YouTubePlaySkill`, `DateTimeSkill`, `SystemStatsSkill`
  - Async Reminders Service (`ReminderService`) with background loop and WebSocket `/ws` broadcast
  - Reminders REST API (`/api/v1/reminders`) with full CRUD support
  - 100% test coverage across OS skills, security constraints, and background scheduling (132/132 backend tests passing)
