"""
Following the live market over the replay WebSocket.

The session layer's own behaviour is covered in test_replay_extend.py. What
matters here is the wiring: the `extend` action exists, it refetches through the
SAME path that created the session, it never drops the socket when a provider
misbehaves, and "now" is measured in the market's timezone rather than the
server's.

That last one is not a detail. Bars are naive Eastern and the deployment box
runs UTC, so a server-clock comparison would judge every bar closed four hours
early -- which is the one failure this design has to avoid, and the one that
would look perfectly fine in local testing on an Eastern machine.
"""

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from api.routers import replay as replay_router
from api import replay_store

client = TestClient(app)

_PARAMS = {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5}


def _body(**over) -> dict:
    body = {
        "symbol": "ES", "timeframe": "5m", "timeframes": ["5m"],
        "data_source": "synthetic",
        "strategy_id": "rsi_divergence", "params": _PARAMS,
        "start_date": "2025-01-01", "end_date": "2025-01-07",
        "session_start": "09:30", "session_end": "16:00",
    }
    body.update(over)
    return body


def _create(**over) -> str:
    r = client.post("/api/replay", json=_body(**over))
    assert r.status_code == 200, r.text
    return r.json()["replay_id"]


def _extend(replay_id: str) -> dict:
    """Send one extend over the socket and return the reply."""
    with client.websocket_connect(f"/api/replay/ws/{replay_id}") as ws:
        ws.send_json({"action": "extend"})
        return ws.receive_json()


class TestMarketNow:
    def test_it_is_eastern_not_the_server_clock(self):
        now = replay_router._market_now()
        expected = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
        assert abs((now - expected).total_seconds()) < 5

    def test_it_is_naive_so_it_compares_with_bar_timestamps(self):
        # Bar timestamps carry no tzinfo. Comparing an aware datetime against one
        # raises TypeError, so this being naive is load-bearing rather than tidy.
        now = replay_router._market_now()
        assert now.tzinfo is None
        assert isinstance(pd.Timestamp("2026-01-05 09:30") < pd.Timestamp(now), bool)

    def test_it_does_not_drift_with_the_process_timezone(self, monkeypatch):
        # A UTC box must still report Eastern. datetime.now(ZoneInfo(...)) is
        # absolute, so this holds without the code consulting the local zone --
        # the test exists to stop someone "simplifying" it to datetime.now().
        monkeypatch.setenv("TZ", "UTC")
        eastern = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
        assert abs((replay_router._market_now() - eastern).total_seconds()) < 5


class TestTheExtendAction:
    def test_the_socket_answers_it(self):
        reply = _extend(_create())
        assert reply["type"] == "extended"

    def test_the_reply_carries_what_the_client_needs(self):
        reply = _extend(_create())
        for key in ("added", "reason", "total_ticks", "bar_counts",
                    "market_time", "data_time", "is_done"):
            assert key in reply, f"missing {key}"

    def test_data_time_is_the_edge_of_the_data(self):
        replay_id = _create()
        reply = _extend(replay_id)
        session = replay_store.get(replay_id).session
        assert reply["data_time"] == session.last_source_time.isoformat()

    def test_an_unknown_action_is_ignored_rather_than_fatal(self):
        replay_id = _create()
        with client.websocket_connect(f"/api/replay/ws/{replay_id}") as ws:
            ws.send_json({"action": "nonsense"})
            ws.send_json({"action": "extend"})
            assert ws.receive_json()["type"] == "extended"

    def test_the_socket_survives_repeated_extends(self):
        replay_id = _create()
        with client.websocket_connect(f"/api/replay/ws/{replay_id}") as ws:
            for _ in range(3):
                ws.send_json({"action": "extend"})
                assert ws.receive_json()["type"] == "extended"


class TestWhenGrowthIsImpossible:
    def test_synthetic_says_so_instead_of_pretending(self):
        reply = _extend(_create(data_source="synthetic"))
        assert reply["added"] == 0
        assert "synthetic" in reply["reason"].lower()
        # Names the fix, not just the problem.
        assert "Schwab" in reply["reason"]

    def test_a_past_session_says_so(self, monkeypatch):
        # external_csv holds ES for 2025, so this creates without touching a broker.
        replay_id = _create(data_source="external_csv",
                            start_date="2025-01-02", end_date="2025-01-03")
        reply = _extend(replay_id)
        assert reply["added"] == 0
        assert "in the past" in reply["reason"]

    def test_a_session_from_before_this_feature_is_handled(self):
        replay_id = _create()
        # A session restored without a request, as an older process would have.
        replay_store.get(replay_id).request = None
        reply = _extend(replay_id)
        assert reply["added"] == 0
        assert "start a new one" in reply["reason"]

    def test_nothing_is_reported_as_zero_not_as_an_error(self):
        # The normal case between bar closes. `added` 0 with a reason is a
        # message; `added` 0 without one is simply "not yet".
        reply = _extend(_create(data_source="external_csv",
                                start_date="2025-01-02", end_date="2025-01-03"))
        assert reply["added"] == 0
        assert reply["is_done"] is False


class TestProviderFailuresDoNotDropTheSocket:
    """
    _extend_session runs inside the WebSocket loop. An exception there kills a
    socket the user is watching, and the UI cannot tell that apart from a network
    drop -- so every provider failure has to come back as a `reason`.
    """

    def _forced_failure(self, monkeypatch, exc):
        replay_id = _create(data_source="external_csv",
                            start_date="2025-01-02", end_date="2025-01-03")
        # Today's date, so the past-session guard does not short-circuit first.
        replay_store.get(replay_id).request.end_date = (
            replay_router._market_now().date() + timedelta(days=1))

        def boom(*a, **k):
            raise exc
        monkeypatch.setattr(replay_router, "_load_bars", boom)
        return _extend(replay_id)

    def test_a_broker_outage_is_reported(self, monkeypatch):
        reply = self._forced_failure(monkeypatch, RuntimeError("connection reset"))
        assert reply["type"] == "extended"
        assert reply["added"] == 0
        assert "could not reach the data source" in reply["reason"]
        assert "connection reset" in reply["reason"]

    def test_an_http_exception_is_reported_with_its_detail(self, monkeypatch):
        from fastapi import HTTPException
        reply = self._forced_failure(
            monkeypatch, HTTPException(400, "No ES 1m data from 'schwab'"))
        assert reply["added"] == 0
        assert "No ES 1m data" in reply["reason"]

    def test_the_session_is_untouched_after_a_failure(self, monkeypatch):
        replay_id = _create(data_source="external_csv",
                            start_date="2025-01-02", end_date="2025-01-03")
        stored = replay_store.get(replay_id)
        stored.request.end_date = replay_router._market_now().date() + timedelta(days=1)
        before = stored.session.total_ticks

        def boom(*a, **k):
            raise RuntimeError("nope")
        monkeypatch.setattr(replay_router, "_load_bars", boom)
        _extend(replay_id)

        assert stored.session.total_ticks == before

    def test_the_socket_still_works_afterwards(self, monkeypatch):
        replay_id = _create(data_source="external_csv",
                            start_date="2025-01-02", end_date="2025-01-03")
        replay_store.get(replay_id).request.end_date = (
            replay_router._market_now().date() + timedelta(days=1))

        def boom(*a, **k):
            raise RuntimeError("nope")
        monkeypatch.setattr(replay_router, "_load_bars", boom)

        with client.websocket_connect(f"/api/replay/ws/{replay_id}") as ws:
            ws.send_json({"action": "extend"})
            assert ws.receive_json()["added"] == 0
            # The real assertion: the connection is still alive.
            ws.send_json({"action": "pause"})
            ws.send_json({"action": "extend"})
            assert ws.receive_json()["type"] == "extended"


#: A weekday inside the CSV corpus, used as the trading day for the growth
#: tests. The date only has to be consistent; the provider is stubbed.
_DAY = date(2025, 1, 2)


def _morning(minutes: int) -> pd.DataFrame:
    """`minutes` one-minute bars from 09:30, well inside a 09:30-16:00 session."""
    idx = pd.DatetimeIndex([
        datetime.combine(_DAY, datetime.min.time()).replace(hour=9, minute=30)
        + timedelta(minutes=i) for i in range(minutes)
    ])
    close = [5000 + i * 0.25 for i in range(minutes)]
    return pd.DataFrame(
        {"open": close, "high": [c + 1 for c in close], "low": [c - 1 for c in close],
         "close": close, "volume": [500 + i for i in range(minutes)]},
        index=idx,
    )


class TestGrowthThroughTheSocket:
    """
    The end-to-end statement, with the provider stubbed so it is deterministic:
    bars that print after the session loaded become playable without restarting.

    The session is built from a MORNING of data rather than a whole day. A
    drained full day sits exactly at 16:00, so every "new" bar lands outside the
    09:30-16:00 window and is filtered away before extend() ever sees it -- which
    is correct behaviour and a useless fixture. Mid-morning is also the real
    situation: the reported case had data ending 09:26.
    """

    def _session_at(self, monkeypatch, minutes: int) -> tuple[str, object]:
        """A drained session holding `minutes` bars, ready to be extended."""
        monkeypatch.setattr(replay_router, "_load_bars",
                            lambda *a, **k: _morning(minutes))
        replay_id = _create(data_source="external_csv",
                            start_date=_DAY.isoformat(), end_date=_DAY.isoformat())
        stored = replay_store.get(replay_id)
        # end_date in the future, so the past-session guard does not fire. The
        # guard itself is covered in TestWhenGrowthIsImpossible.
        stored.request.end_date = replay_router._market_now().date() + timedelta(days=1)
        while not stored.session.is_done:
            stored.session.tick()
        return replay_id, stored

    def test_new_bars_arrive_and_become_playable(self, monkeypatch):
        replay_id, stored = self._session_at(monkeypatch, 60)
        session = stored.session
        assert session.is_done
        before = session.total_ticks

        # The provider now knows about ten more minutes.
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(70))
        monkeypatch.setattr(replay_router, "_market_now",
                            lambda: datetime.combine(_DAY, datetime.min.time())
                            .replace(hour=12))

        reply = _extend(replay_id)

        assert reply["reason"] is None
        # `added` counts SOURCE bars, which are one-minute regardless of what is
        # selected -- see _source_timeframe.
        assert reply["added"] == 10
        # Ticks are counted in BASE bars, and this session's base is 5m, so ten
        # new minutes are two new ticks. The two numbers are in different units
        # on purpose; conflating them is how a progress bar ends up lying.
        assert reply["total_ticks"] == before + 2
        # The point of the whole feature: a finished session is running again.
        assert reply["is_done"] is False
        assert not session.is_done

    def test_the_new_bars_actually_play(self, monkeypatch):
        replay_id, stored = self._session_at(monkeypatch, 60)
        session = stored.session
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(70))
        monkeypatch.setattr(replay_router, "_market_now",
                            lambda: datetime.combine(_DAY, datetime.min.time())
                            .replace(hour=12))
        end_of_snapshot = session.market_time
        _extend(replay_id)

        played = 0
        while not session.is_done:
            session.tick()
            played += 1

        # Two 5m ticks covering the ten new minutes.
        assert played == 2
        assert session.market_time == end_of_snapshot + timedelta(minutes=10)

    def test_the_still_forming_bar_is_withheld_end_to_end(self, monkeypatch):
        replay_id, stored = self._session_at(monkeypatch, 60)
        grown = _morning(62)
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: grown)
        # Polled 30 seconds into the last new bar: only the first of the two has
        # closed, so only one may be taken.
        monkeypatch.setattr(
            replay_router, "_market_now",
            lambda: (grown.index[-1] + timedelta(seconds=30)).to_pydatetime())

        reply = _extend(replay_id)

        assert reply["added"] == 1
        assert reply["data_time"] == grown.index[-2].isoformat()

    def test_polling_again_picks_up_the_withheld_bar(self, monkeypatch):
        replay_id, stored = self._session_at(monkeypatch, 60)
        grown = _morning(62)
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: grown)

        monkeypatch.setattr(replay_router, "_market_now",
                            lambda: (grown.index[-1]).to_pydatetime())
        assert _extend(replay_id)["added"] == 1
        # A minute later the held-back bar has closed.
        monkeypatch.setattr(
            replay_router, "_market_now",
            lambda: (grown.index[-1] + timedelta(minutes=1)).to_pydatetime())
        second = _extend(replay_id)
        assert second["added"] == 1
        assert second["data_time"] == grown.index[-1].isoformat()

    def test_a_quiet_poll_reports_nothing_without_complaining(self, monkeypatch):
        replay_id, stored = self._session_at(monkeypatch, 60)
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(60))
        monkeypatch.setattr(replay_router, "_market_now",
                            lambda: datetime.combine(_DAY, datetime.min.time())
                            .replace(hour=12))
        reply = _extend(replay_id)
        assert reply["added"] == 0
        assert reply["reason"] is None
        assert reply["is_done"] is True


class TestTheSessionNeverLoadsAFormingBar:
    """
    Found against the live provider, not in a fixture.

    A session created at 11:05:35 ET loaded a bar stamped 11:05 holding 35
    seconds of trade and replayed it as closed. The first attempt to follow the
    market was then REFUSED -- correctly, by the revised-history guard -- because
    the bar it had already replayed changed as soon as the minute completed.

    So the trim is what makes following possible at all. It also fixes the
    displayed bar on its own account: the last row of the tape was not a bar.
    """

    def test_the_forming_bar_is_trimmed(self, monkeypatch):
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(61))
        # 09:30 + 60 minutes = 10:30, polled 20 seconds in. The 10:30 bar has not
        # closed, so 60 bars may be loaded, not 61.
        monkeypatch.setattr(
            replay_router, "_market_now",
            lambda: datetime.combine(_DAY, datetime.min.time())
            .replace(hour=10, minute=30, second=20))

        replay_id = _create(data_source="external_csv",
                            start_date=_DAY.isoformat(), end_date=_DAY.isoformat())
        session = replay_store.get(replay_id).session
        assert len(session._source_df) == 60
        assert session.last_source_time == pd.Timestamp(f"{_DAY} 10:29")

    def test_a_closed_final_bar_is_kept(self, monkeypatch):
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(61))
        # A second past its close: the 10:30 bar is complete and stays.
        monkeypatch.setattr(
            replay_router, "_market_now",
            lambda: datetime.combine(_DAY, datetime.min.time())
            .replace(hour=10, minute=31, second=1))
        replay_id = _create(data_source="external_csv",
                            start_date=_DAY.isoformat(), end_date=_DAY.isoformat())
        assert len(replay_store.get(replay_id).session._source_df) == 61

    def test_the_live_failure_no_longer_happens(self, monkeypatch):
        """
        The exact sequence that failed: create mid-minute, drain, then refetch
        once that minute has completed. Previously refused as revised history.
        """
        at_creation = datetime.combine(_DAY, datetime.min.time()).replace(
            hour=10, minute=30, second=35)
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(61))
        monkeypatch.setattr(replay_router, "_market_now", lambda: at_creation)

        replay_id = _create(data_source="external_csv",
                            start_date=_DAY.isoformat(), end_date=_DAY.isoformat())
        stored = replay_store.get(replay_id)
        stored.request.end_date = at_creation.date() + timedelta(days=1)
        while not stored.session.is_done:
            stored.session.tick()

        # A minute later the provider serves the SAME 61 bars, but now the last
        # one is complete and its values differ from the partial version.
        later = at_creation.replace(minute=31, second=40)
        monkeypatch.setattr(replay_router, "_market_now", lambda: later)
        reply = _extend(replay_id)

        assert reply["reason"] is None, f"still refused: {reply['reason']}"
        assert reply["added"] == 1
        assert reply["data_time"] == f"{_DAY}T10:30:00"

    def test_synthetic_data_is_left_alone(self):
        # Generated bars are not observations and can legitimately sit past the
        # wall clock; trimming them to "now" would silently shorten a session.
        replay_id = _create(data_source="synthetic")
        assert replay_store.get(replay_id).session.total_ticks > 0

    def test_a_session_with_no_closed_bar_yet_says_so(self, monkeypatch):
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(1))
        monkeypatch.setattr(
            replay_router, "_market_now",
            lambda: datetime.combine(_DAY, datetime.min.time())
            .replace(hour=9, minute=30, second=10))
        r = client.post("/api/replay", json=_body(
            data_source="external_csv",
            start_date=_DAY.isoformat(), end_date=_DAY.isoformat()))
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "closed yet" in detail
        # Says what to do about it, not just what went wrong.
        assert "earlier date" in detail

    def test_historical_sessions_are_unaffected(self, monkeypatch):
        # Every bar of a past day is long closed, so the trim is a no-op there.
        monkeypatch.setattr(replay_router, "_load_bars", lambda *a, **k: _morning(60))
        replay_id = _create(data_source="external_csv",
                            start_date=_DAY.isoformat(), end_date=_DAY.isoformat())
        assert len(replay_store.get(replay_id).session._source_df) == 60


class TestTheRefetchUsesTheOriginalRequest:
    def test_the_request_is_kept_on_the_session(self):
        replay_id = _create(symbol="ES", data_source="synthetic")
        stored = replay_store.get(replay_id)
        assert stored.request is not None
        assert stored.request.symbol == "ES"
        assert stored.request.session_start is not None

    def test_the_refetch_passes_that_request_through_unchanged(self, monkeypatch):
        replay_id = _create(data_source="external_csv",
                            start_date="2025-01-02", end_date="2025-01-03")
        stored = replay_store.get(replay_id)
        stored.request.end_date = replay_router._market_now().date() + timedelta(days=1)

        seen = {}

        def spy(req, source_tf, spec):
            seen["req"] = req
            seen["source_tf"] = source_tf
            return stored.session._source_df

        monkeypatch.setattr(replay_router, "_load_bars", spy)
        _extend(replay_id)

        assert seen["req"] is stored.request
        # 1m regardless of the selected timeframes -- the VWAP reason in
        # _source_timeframe applies just as much to a refetch.
        assert seen["source_tf"] == "1m"
