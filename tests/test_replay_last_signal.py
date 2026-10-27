"""Every replay frame carries the pane's LAST signal, not just this bar's.

Reported 2026-10-27: after a session was rebuilt (the server restarted, so the
client re-created it and seeked back to where it was), Market Grid's "Last
signal" column went blank on most timeframes -- including one holding a SHORT
position, which cannot exist without a signal. A seek sends only the final
frame, and `signal` is only the signal fired ON that bar, so every earlier
signal was lost. `last_signal` is the most recent signal the pane has fired,
whatever bar it fired on.
"""

from fastapi.testclient import TestClient

from api import replay_store
from api.main import app

client = TestClient(app)

TFS = ["1m", "5m"]
BODY = {
    "symbol": "ES", "timeframes": TFS, "data_source": "synthetic",
    "strategy_id": "rsi_divergence",
    # Wide thresholds so the synthetic day actually produces signals.
    "params": {"rsi_overbought": 60, "rsi_oversold": 40, "swing_lookback": 2},
    "start_date": "2026-08-17", "end_date": "2026-08-18",
    "session_start": None, "session_end": None,
}
SEEK_TO = 300


def _expected_last_signals() -> dict[str, dict | None]:
    """Step an identical session bar by bar, remembering each pane's last signal."""
    r = client.post("/api/replay", json=BODY)
    assert r.status_code == 200, r.text
    session = replay_store.get(r.json()["replay_id"]).session
    last: dict[str, dict | None] = {tf: None for tf in TFS}
    while session.progress()[0] < SEEK_TO and not session.is_done:
        for tf, frame in session.tick().items():
            if frame.signal is not None:
                last[tf] = {"type": frame.signal.signal_type.value, "reason": frame.signal.reason}
    return last


def test_a_seek_keeps_every_panes_last_signal():
    want = _expected_last_signals()
    assert any(v is not None for v in want.values()), "no signals by tick 300 -- widen the params"

    r = client.post("/api/replay", json=BODY)
    assert r.status_code == 200, r.text
    with client.websocket_connect(f"/api/replay/ws/{r.json()['replay_id']}") as ws:
        ws.send_json({"action": "seek", "ticks": SEEK_TO})
        msg = ws.receive_json()
    assert msg["type"] == "frames"
    for tf, frame in msg["frames"].items():
        assert frame["last_signal"] == want[tf], tf


def test_last_signal_is_this_bars_signal_when_one_fired():
    r = client.post("/api/replay", json=BODY)
    session = replay_store.get(r.json()["replay_id"]).session
    from api.serializers import frame_to_dict
    seen = False
    while not session.is_done and not seen:
        for frame in session.tick().values():
            d = frame_to_dict(frame)
            if d["signal"] is not None:
                assert d["last_signal"] == d["signal"]
                seen = True
    assert seen
