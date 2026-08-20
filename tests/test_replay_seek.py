"""
Fast-forwarding a rebuilt session back to where the tape was.

Sessions live in a dict in this process, so a deploy, a crash or an OOM kill
takes every running replay with it. Recovery re-creates the session from the
same configuration and seeks; without a seek, recovering meant starting the
tape again from bar one.
"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _create() -> str:
    r = client.post("/api/replay", json={
        "symbol": "ES", "timeframe": "5m", "data_source": "synthetic",
        "strategy_id": "rsi_divergence",
        "start_date": "2026-08-17", "end_date": "2026-08-18",
        "session_start": None, "session_end": None,
    })
    assert r.status_code == 200, r.text
    return r.json()["replay_id"]


def test_seek_lands_exactly_on_the_requested_tick():
    rid = _create()
    with client.websocket_connect(f"/api/replay/ws/{rid}") as ws:
        ws.send_json({"action": "seek", "ticks": 25})
        frame = ws.receive_json()
        assert frame["type"] == "frames"
        assert frame["ticks_processed"] == 25
        assert ws.receive_json() == {"type": "seeked", "ticks_processed": 25}


def test_seek_does_not_start_playback():
    """Recovery restores position; whether to resume is the client's decision."""
    rid = _create()
    with client.websocket_connect(f"/api/replay/ws/{rid}") as ws:
        ws.send_json({"action": "seek", "ticks": 10})
        ws.receive_json()
        assert ws.receive_json()["ticks_processed"] == 10
        # Ask again for the same tick: already there, so nothing advances.
        ws.send_json({"action": "seek", "ticks": 10})
        ws.receive_json()
        assert ws.receive_json()["ticks_processed"] == 10


def test_seek_past_the_end_stops_at_the_end():
    """A stale cursor from a longer session must not spin forever."""
    rid = _create()
    with client.websocket_connect(f"/api/replay/ws/{rid}") as ws:
        ws.send_json({"action": "seek", "ticks": 10_000_000})
        frame = ws.receive_json()
        done = ws.receive_json()
        assert done["type"] == "seeked"
        assert done["ticks_processed"] == frame["total_ticks"]


def test_seek_to_zero_is_a_no_op():
    rid = _create()
    with client.websocket_connect(f"/api/replay/ws/{rid}") as ws:
        ws.send_json({"action": "seek", "ticks": 0})
        ws.receive_json()
        assert ws.receive_json()["ticks_processed"] == 0
