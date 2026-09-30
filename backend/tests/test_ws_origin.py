import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.api.v1.websocket import is_allowed_origin
from backend.app.main import create_app


def test_is_allowed_origin_unit() -> None:
    allowed = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # Valid origins
    assert is_allowed_origin("http://127.0.0.1:5173", allowed) is True
    assert is_allowed_origin("http://127.0.0.1:5173/", allowed) is True
    assert is_allowed_origin("http://localhost:5173", allowed) is True

    # Untrusted external origins
    assert is_allowed_origin("http://evil.com", allowed) is False
    assert is_allowed_origin("https://malicious-site.net", allowed) is False
    assert is_allowed_origin("http://localhost:3000", allowed) is False

    # Native client (no origin header)
    assert is_allowed_origin(None, allowed) is True


def test_websocket_accepts_authorized_origin() -> None:
    app = create_app()
    with TestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as websocket:
            websocket.send_json({"type": "ping", "timestamp": 123456})
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert response["timestamp"] == 123456


def test_websocket_rejects_unauthorized_origin() -> None:
    app = create_app()
    with TestClient(app) as client:
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/ws", headers={"origin": "http://attacker-site.com"}),
        ):
            pass

    # 1008 is WS_POLICY_VIOLATION
    assert exc_info.value.code == 1008

