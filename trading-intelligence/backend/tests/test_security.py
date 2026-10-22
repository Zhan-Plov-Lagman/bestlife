import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.database import db_engine, metadata
from app.main import app, requests_window
from app.security import AccessPolicy


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "security.db"))
    metadata.create_all(db_engine())
    requests_window.clear()
    with TestClient(app) as client:
        yield client


def test_expired_wrong_missing_session_and_size(client):
    for token in ("", "wrong"):
        assert (
            client.post(
                "/api/control", json={"action": "start"}, headers={"X-CSRF-Token": token}
            ).status_code
            == 403
        )
    token = client.get("/api/session").json()["csrf"]
    app.state.runtime.access.sessions[token] = time.monotonic() - 1
    assert (
        client.post(
            "/api/control", json={"action": "start"}, headers={"X-CSRF-Token": token}
        ).status_code
        == 403
    )
    token = client.get("/api/session").json()["csrf"]
    assert (
        client.post(
            "/api/control", content=b"x" * 65537, headers={"X-CSRF-Token": token}
        ).status_code
        == 413
    )


def test_remote_scope_and_local_peer(monkeypatch):
    local = AccessPolicy()
    assert not local.authorize("192.168.1.1", "", True)
    monkeypatch.setenv("MERIDIAN_REMOTE_MODE", "true")
    with pytest.raises(ValueError):
        AccessPolicy()
    monkeypatch.setenv("MERIDIAN_READ_TOKEN", "r" * 32)
    monkeypatch.setenv("MERIDIAN_CONTROL_TOKEN", "c" * 32)
    remote = AccessPolicy()
    assert remote.authorize("192.168.1.1", "Bearer " + "r" * 32, False)
    assert not remote.authorize("192.168.1.1", "Bearer " + "r" * 32, True)
    assert not remote.authorize("127.0.0.1", "", True)


def test_remote_session_not_public(client):
    app.state.runtime.access.remote = True
    app.state.runtime.access.read_token = "r" * 32
    app.state.runtime.access.control_token = "c" * 32
    assert client.get("/api/session").status_code == 403
    assert (
        client.get("/api/session", headers={"Authorization": "Bearer " + "r" * 32}).status_code
        == 403
    )
    assert (
        client.get("/api/state", headers={"Authorization": "Bearer " + "r" * 32}).status_code == 200
    )
    assert (
        client.get("/api/session", headers={"Authorization": "Bearer " + "c" * 32}).status_code
        == 200
    )


@pytest.mark.parametrize("hello", [{}, {"csrf": "invalid"}, []])
def test_websocket_denies_invalid_access(client, hello):
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as ws:
        ws.send_json(hello)
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_websocket_expired_token(client):
    token = client.get("/api/session").json()["csrf"]
    app.state.runtime.access.sessions[token] = time.monotonic() - 1
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as ws:
        ws.send_json({"csrf": token})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
