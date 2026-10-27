"""A rebuilt session gives every pane back its WHOLE history.

Reported 2026-10-27 after the server restarted mid-session: Market Grid
re-creates the session and seeks to where it was, but a seek sent only the
final frame. The client had cleared every pane, so each was left holding the
bars from the seek onwards -- 1m and 3m, which lose the most bars, showed a
VA High of 4711.42 / 4806.10 where their full data gives 4873.73, and "Last
signal" went blank.

After a seek the server now sends a `restored` message: for EVERY pane, all
its closed bars (no 500-bar cap -- a 1m profile over two days needs more)
and its current state, whether or not that pane closed a bar on the final
tick.
"""

from fastapi.testclient import TestClient

from api import replay_store
from api.main import app

client = TestClient(app)

TFS = ["1m", "5m", "1h"]
BODY = {
    "symbol": "ES", "timeframes": TFS, "data_source": "synthetic",
    "strategy_id": "rsi_divergence",
    "params": {"rsi_overbought": 60, "rsi_oversold": 40, "swing_lookback": 2},
    "start_date": "2026-08-17", "end_date": "2026-08-19",
    "session_start": None, "session_end": None,
}
SEEK_TO = 700     # past 500 1m bars, and not on an hour boundary


def _seek(ticks: int) -> list[dict]:
    r = client.post("/api/replay", json=BODY)
    assert r.status_code == 200, r.text
    with client.websocket_connect(f"/api/replay/ws/{r.json()['replay_id']}") as ws:
        ws.send_json({"action": "seek", "ticks": ticks})
        return [ws.receive_json() for _ in range(3)]


def _reference(ticks: int):
    """The same session stepped bar by bar: each pane's bars and last frame."""
    r = client.post("/api/replay", json=BODY)
    session = replay_store.get(r.json()["replay_id"]).session
    last = {}
    while session.progress()[0] < ticks and not session.is_done:
        last.update(session.tick())
    return session, last


def test_seek_is_followed_by_a_full_restore_then_seeked():
    frames, restored, seeked = _seek(SEEK_TO)
    assert frames["type"] == "frames"
    assert restored["type"] == "restored"
    assert seeked == {"type": "seeked", "ticks_processed": SEEK_TO}
    assert set(restored["backfill"]) == set(TFS)


def test_every_pane_gets_all_its_closed_bars_with_no_cap():
    _, restored, _ = _seek(SEEK_TO)
    session, _ = _reference(SEEK_TO)
    for tf in TFS:
        bf = restored["backfill"][tf]
        pane = session.panes[tf]
        assert bf["bars_closed"] == pane.cursor
        assert len(bf["bars"]) == pane.cursor, f"{tf}: history truncated"
        assert bf["truncated"] is False
        assert [b["t"] for b in bf["bars"]] == [s.isoformat() for s in pane.df.index[:pane.cursor]]
    assert len(restored["backfill"]["1m"]["bars"]) > 500


def test_every_pane_gets_its_current_state_even_if_it_did_not_close_on_the_last_tick():
    _, restored, _ = _seek(SEEK_TO)
    _, last = _reference(SEEK_TO)
    for tf in TFS:
        state = restored["backfill"][tf]["state"]
        assert state is not None, tf
        frame = last[tf]
        assert state["bars_processed"] == frame.bars_processed
        assert state["position"] == frame.position
        want = ({"type": frame.last_signal.signal_type.value, "reason": frame.last_signal.reason}
                if frame.last_signal else None)
        assert state["last_signal"] == want
