from fastapi.testclient import TestClient

from app.database import db_engine, metadata
from app.main import app, requests_window


def test_controls_origin_and_websocket(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "api.db"))
    metadata.create_all(db_engine())
    requests_window.clear()
    with TestClient(app) as client:
        assert client.post("/api/control", json={"action": "start"}).status_code == 403
        csrf = client.get("/api/session").json()["csrf"]
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        assert client.post("/api/control", json={"action": "start"}, headers=headers).json()[
            "running"
        ]
        assert client.post("/api/control", json={"action": "kill"}, headers=headers).json()[
            "killed"
        ]
        assert client.get("/api/state", headers={"Origin": "https://evil.test"}).status_code == 403
        with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as ws:
            ws.send_json({"csrf": csrf})
            assert ws.receive_json()["paper_only"]
