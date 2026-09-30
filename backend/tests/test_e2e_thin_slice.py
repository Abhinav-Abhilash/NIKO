import json
from collections.abc import AsyncIterator, Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token
from backend.app.llm.types import LLMMessage, NormalizedToolCall, StreamChunk
from backend.app.main import create_app


@pytest.fixture(autouse=True)
def disable_background_workers_for_e2e() -> Generator[None, None, None]:
    with (
        patch("backend.app.services.metrics_service.MetricsService.start_collector", new_callable=AsyncMock),
        patch("backend.app.services.metrics_service.MetricsService.stop_collector", new_callable=AsyncMock),
        patch("backend.app.services.reminder_service.ReminderService.start_background_worker", new_callable=AsyncMock),
        patch("backend.app.services.reminder_service.ReminderService.stop_background_worker", new_callable=AsyncMock),
        patch("backend.app.llm.deferred_queue.DeferredQueue.start_worker"),
        patch("backend.app.llm.deferred_queue.DeferredQueue.stop_worker"),
    ):
        yield


class FakeLLMProvider:
    """
    Predictable fake LLM provider for Phase 1 end-to-end multi-turn testing:
    - Turn 1: Detects 'what time is it and how's my CPU' -> emits tool calls for datetime and system_stats.
              On next iteration, streams the final answer formatted with the real tool results.
    - Turn 2: Detects 'open notepad' -> emits tool call for open_app with {'app_name': 'notepad'}.
    """

    def __init__(self) -> None:
        self.call_history: list[list[LLMMessage]] = []

    async def chat_stream(
        self,
        role: Any,
        messages: list[LLMMessage],
        tools: Any = None,
    ) -> AsyncIterator[StreamChunk]:
        _ = role
        _ = tools
        self.call_history.append(messages)

        # Check last user message and tool messages
        user_msgs = [m for m in messages if m.role == "user"]
        tool_msgs = [m for m in messages if m.role == "tool"]
        latest_user = user_msgs[-1].content if user_msgs else ""

        if "what time is it and how's my CPU" in latest_user:
            # If tools have not been executed yet in this turn
            datetime_tools = [m for m in tool_msgs if m.name == "datetime"]
            sys_tools = [m for m in tool_msgs if m.name == "system_stats"]

            if not datetime_tools or not sys_tools:
                # Yield tool calls for both skills
                yield StreamChunk(
                    tool_calls=[
                        NormalizedToolCall(
                            id="tc_e2e_datetime_1",
                            name="datetime",
                            arguments={},
                        ),
                        NormalizedToolCall(
                            id="tc_e2e_sysstats_1",
                            name="system_stats",
                            arguments={},
                        ),
                    ]
                )
            else:
                # Both tools have executed! Extract real tool results
                dt_data = json.loads(datetime_tools[-1].content)
                sys_data = json.loads(sys_tools[-1].content)

                time_str = dt_data.get("time", "12:00:00")
                cpu_pct = sys_data.get("cpu", {}).get("percent", 0.0)

                yield StreamChunk(content=f"The current time is {time_str} ")
                yield StreamChunk(content=f"and CPU utilization is {cpu_pct}%.")

        elif "open notepad" in latest_user:
            # Yield CONFIRM-tier open_app tool call
            yield StreamChunk(
                tool_calls=[
                    NormalizedToolCall(
                        id="tc_e2e_open_app_1",
                        name="open_app",
                        arguments={"app_name": "notepad"},
                    )
                ]
            )

        else:
            yield StreamChunk(content="Echo: " + latest_user)


def test_phase1_thin_slice_end_to_end() -> None:
    """
    Automated Thin End-to-End Slice Test (Phase 1):
    Turn 1: User types 'what time is it and how's my CPU'
            -> Streams answer using real datetime & system_stats skills.
    Turn 2: User types 'open notepad'
            -> Triggers human confirmation modal (approval required).
            -> User approves (Enter / POST respond).
            -> open_app launches Notepad on Windows host.
    """
    app = create_app()
    settings = get_settings()

    valid_token = create_jwt_token(
        payload={"sub": "e2e_user_id", "username": "e2e_owner", "role": "owner"},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=30),
    )

    fake_llm = FakeLLMProvider()

    mock_process = MagicMock()
    mock_process.pid = 98765

    with (
        patch("subprocess.Popen", return_value=mock_process) as mock_popen,
        patch("backend.app.llm.orchestrator.LLMOrchestrator.chat_stream", side_effect=fake_llm.chat_stream),
        TestClient(app) as client,
        client.websocket_connect(
            f"/ws?token={valid_token}",
            headers={"origin": "http://localhost:5173"},
        ) as ws,
    ):
        # -------------------------------------------------------------
        # TURN 1: 'what time is it and how's my CPU'
        # -------------------------------------------------------------
        turn1_req_id = "req_e2e_turn_1"
        ws.send_json({
            "type": "chat",
            "request_id": turn1_req_id,
            "content": "what time is it and how's my CPU",
        })

        executed_tools: list[str] = []
        streamed_chunks: list[str] = []
        turn1_done = False
        conversation_id: str | None = None

        for _ in range(20):
            msg = ws.receive_json()
            mtype = msg.get("type")

            if mtype == "chat:error":
                pytest.fail(f"Turn 1 unexpected chat error: {msg}")

            if mtype == "chat:tool_call":
                executed_tools.append(msg.get("name"))

            elif mtype == "chat:tool_result":
                tool_name = msg.get("name")
                res = msg.get("result")
                assert msg.get("status") == "completed"
                if tool_name == "datetime":
                    assert "time" in res
                    assert "date" in res
                elif tool_name == "system_stats":
                    assert "cpu" in res
                    assert "ram" in res

            elif mtype == "chat:chunk":
                streamed_chunks.append(msg.get("chunk", ""))

            elif mtype == "chat:done":
                turn1_done = True
                conversation_id = msg.get("response", {}).get("conversation_id")
                break

        assert "datetime" in executed_tools
        assert "system_stats" in executed_tools
        assert turn1_done is True
        assert conversation_id is not None

        full_turn1_answer = "".join(streamed_chunks)
        assert "The current time is" in full_turn1_answer
        assert "CPU utilization is" in full_turn1_answer

        # -------------------------------------------------------------
        # TURN 2: 'open notepad'
        # -------------------------------------------------------------
        turn2_req_id = "req_e2e_turn_2"
        ws.send_json({
            "type": "chat",
            "request_id": turn2_req_id,
            "conversation_id": conversation_id,
            "content": "open notepad",
        })

        approval_required_event: dict[str, Any] | None = None
        turn2_done = False

        for _ in range(15):
            msg = ws.receive_json()
            mtype = msg.get("type")

            if mtype == "chat:error":
                pytest.fail(f"Turn 2 unexpected chat error: {msg}")

            if mtype == "chat:approval_required":
                approval_required_event = msg

            elif mtype == "chat:done":
                turn2_done = True
                break

        assert approval_required_event is not None, "chat:approval_required event was not emitted!"
        assert turn2_done is True

        approval_data = approval_required_event.get("approval", {})
        approval_id = approval_data.get("approval_id")
        assert approval_id is not None
        assert approval_data.get("args_hash") is not None

        # Ensure notepad has not been launched prior to human confirmation
        mock_popen.assert_not_called()

        # -------------------------------------------------------------
        # SIMULATE USER DECISION: Press Enter / Click Approve
        # -------------------------------------------------------------
        approval_response = client.post(
            f"/api/v1/approvals/{approval_id}/respond",
            headers={
                "Authorization": f"Bearer {valid_token}",
                "Origin": "http://localhost:5173",
            },
            json={
                "decision": "approve",
            },
        )

        assert approval_response.status_code == 200
        resp_data = approval_response.json()
        assert resp_data["status"] == "approved"
        assert resp_data["id"] == approval_id

        # Verify open_app skill executed and launched notepad
        mock_popen.assert_called_once()
        call_args, call_kwargs = mock_popen.call_args
        launch_cmd = call_args[0]

        assert any("notepad.exe" in str(arg).lower() for arg in launch_cmd)
