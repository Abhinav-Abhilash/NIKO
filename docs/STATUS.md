# NIKO Project Status

Current Milestone: **Milestone 4 - Multi-Provider LLM & Chat**

## Current Progress
- [x] Architecture & Model Registry definition (`docs/MODELS.md`)
- [x] Gemini Provider (`gemini-2.0-flash`, `gemini-2.0-flash-lite`) with SSE streaming & tool calling
- [x] Groq Provider (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`, etc.) with LPU streaming
- [x] OpenRouter Provider (`openrouter/free`, `qwen/qwen-2.5-coder-32b-instruct:free`) for code role fallback
- [x] Predictive Cooldown Tracker & Live Model Discovery Service
- [x] Multi-Provider LLM Orchestrator with role fallback, cooldown avoidance, and tool output pruning
- [x] Model Roles & Settings Persistence + Admin Endpoints
- [x] a. Key redaction in structlog & uvicorn logs
- [x] b. ChatService (history, sliding context, tool dispatch via SkillService/Guard, provenance tagging, untrusted content wrapping, non-refusing system prompt)
- [x] c. WebSocket chat streaming (`chat:chunk`, `chat:tool_call`, cancellation)
- [ ] d. Quota-exhaustion deferred queue + cooldown banner + automatic retry
- [ ] e. Tests, CHANGELOG, README, and ADR for model roles and fallback
- [ ] f. Final CI verification & push

Next Step: **Task d - Quota-Exhaustion Deferred Queue & Cooldown Banner**
