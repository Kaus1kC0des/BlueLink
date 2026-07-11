"""Integration test: drive the FastAPI app over a real WebSocket.

Uses BLUELINK_FAKE so no BLE hardware is touched. This exercises the server +
dispatch + event-broadcast plumbing end to end.
"""

import os

import pytest
from starlette.testclient import TestClient

from bluelink.config import Config
from bluelink.web.server import build_app


@pytest.fixture
def client(tmp_path):
    os.environ["BLUELINK_FAKE"] = "1"
    cfg = Config(data_dir=tmp_path)
    app = build_app(cfg, save_name=lambda n: n, initial_name="Tester")
    with TestClient(app) as c:
        yield c
    os.environ.pop("BLUELINK_FAKE", None)


def _drain_until(ws, pred, limit=10):
    for _ in range(limit):
        ev = ws.receive_json()
        if pred(ev):
            return ev
    raise AssertionError("expected event not received")


def test_status_on_connect(client):
    with client.websocket_connect("/ws") as ws:
        ev = ws.receive_json()
        assert ev["t"] == "status"
        assert ev["role"] == "idle"
        assert ev["name"] == "Tester"


def test_host_command_flow(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # initial status
        ws.send_json({"t": "host"})
        ev = _drain_until(ws, lambda e: e["t"] == "status" and e["role"] == "host")
        assert ev["state"] == "advertising"


def test_send_without_connection_errors(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"t": "send", "body": "hi"})
        ev = _drain_until(ws, lambda e: e["t"] == "error")
        assert ev["code"] == "not_connected"


def test_bad_command_reports_error(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"t": "frobnicate"})
        ev = _drain_until(ws, lambda e: e["t"] == "error")
        assert ev["code"] == "bad_command"


def test_root_served(client):
    # Serves the built React app if ui/dist exists, else the placeholder page.
    # Either way the root must be reachable and identify as BlueLink.
    resp = client.get("/")
    assert resp.status_code == 200
    assert "BlueLink" in resp.text
