from datetime import timedelta

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.core.security import create_jwt_token
from backend.app.main import create_app


def test_ws_ping_pong_heartbeat() -> None:
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        ws.send_json({"type": "ping", "timestamp": "2026-09-29T12:00:00Z"})
        response = ws.receive_json()
        assert response["type"] == "pong"
        assert response["timestamp"] == "2026-09-29T12:00:00Z"


def test_ws_query_param_and_message_auth() -> None:
    app = create_app()
    client = TestClient(app)
    settings = get_settings()

    valid_token = create_jwt_token(
        payload={"sub": "user_123", "username": "owner", "role": "owner"},
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        expires_delta=timedelta(minutes=15),
    )

    # 1. Connect with token in query params
    with client.websocket_connect(
        f"/ws?token={valid_token}", headers={"origin": "http://localhost:5173"}
    ) as ws:
        ws.send_json({"type": "ping"})
        res = ws.receive_json()
        assert res["type"] == "pong"

    # 2. Connect without token, then authenticate via 'auth' message
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        # Valid token message
        ws.send_json({"type": "auth", "token": valid_token})
        auth_res = ws.receive_json()
        assert auth_res["type"] == "auth_ok"
        assert auth_res["user_id"] == "user_123"

        # Invalid token message
        ws.send_json({"type": "auth", "token": "invalid.jwt.token"})
        err_res = ws.receive_json()
        assert err_res["type"] == "auth_error"

        # Missing token message
        ws.send_json({"type": "auth"})
        missing_res = ws.receive_json()
        assert missing_res["type"] == "auth_error"


def test_ws_topic_subscription() -> None:
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        # Subscribe to specific topics
        ws.send_json({"type": "subscribe", "topics": ["sys", "approval"]})
        sub_res = ws.receive_json()
        assert sub_res["type"] == "subscribed"
        assert set(sub_res["topics"]) == {"sys", "approval"}

        # Invalid subscription payload
        ws.send_json({"type": "subscribe", "topics": "not-a-list"})
        err_res = ws.receive_json()
        assert err_res["type"] == "error"

        # General ack
        ws.send_json({"type": "other_action"})
        ack_res = ws.receive_json()
        assert ack_res["type"] == "ack"
        assert ack_res["received"] == "other_action"
