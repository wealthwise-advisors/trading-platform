"""A chart on live data keeps moving; anything else stays exactly as it was."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import store
from api.main import app
from api.routers import backtests

client = TestClient(app)


def _bars(start, n):
    idx = pd.date_range(start, periods=n, freq="1min")
    return pd.DataFrame({"open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 5.0}, index=idx)


@pytest.fixture
def run(monkeypatch):
    """A stored run on 'schwab' data, three bars old, ending tomorrow."""
    r = client.post("/api/backtests", json={
        "symbol": "ES", "timeframe": "1m", "data_source": "synthetic", "strategy_id": "rsi_divergence",
        "params": {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5},
        "start_date": "2026-11-06", "end_date": "2026-11-09",
    })
    assert r.status_code == 200, r.text[:300]
    bid = r.json()["backtest_id"]
    stored = next(v for k, v in store._store.items() if k[1] == bid)
    stored.data_source = "schwab"
    now = datetime.now().replace(second=0, microsecond=0)
    stored.results.price_data = _bars(now - timedelta(days=2), 3)
    stored.results.end_date = now + timedelta(days=3)
    stored.session_start = stored.session_end = None
    return bid, stored


def _provider(monkeypatch, load):
    calls = []
    def build(*a, **k):
        def wrapped(*la):
            calls.append(la)
            return load(*la)
        return SimpleNamespace(load=wrapped)
    monkeypatch.setattr(backtests, "_build_provider", build)
    return calls


def test_new_bars_are_added_and_the_forming_bar_replaced(run, monkeypatch):
    bid, stored = run
    last = stored.results.price_data.index[-1]
    fresh = _bars(last, 2)
    fresh.loc[last, "close"] = 99.0
    _provider(monkeypatch, lambda *a: fresh)
    body = client.post(f"/api/backtests/{bid}/live-refresh").json()
    assert body["live"] is True
    assert len(body["bars"]) == 4
    assert body["bars"][2]["c"] == 99.0
    assert len({b["t"] for b in body["bars"]}) == 4


def test_indicators_grow_with_the_bars(run, monkeypatch):
    bid, stored = run
    _provider(monkeypatch, lambda *a: _bars(stored.results.price_data.index[-1], 3))
    body = client.post(f"/api/backtests/{bid}/live-refresh").json()
    assert len(body["indicators"]["rsi2"]) == len(body["bars"]) == 5


def test_no_new_bars_changes_nothing(run, monkeypatch):
    bid, stored = run
    _provider(monkeypatch, lambda *a: _bars("2020-01-01", 0))
    assert len(client.post(f"/api/backtests/{bid}/live-refresh").json()["bars"]) == 3


def test_a_failed_fetch_keeps_the_chart_and_keeps_polling(run, monkeypatch):
    bid, _ = run
    def boom(*a):
        raise RuntimeError("Schwab tokens are missing or expired.")
    _provider(monkeypatch, boom)
    r = client.post(f"/api/backtests/{bid}/live-refresh")
    assert r.status_code == 200
    assert r.json()["live"] is True and len(r.json()["bars"]) == 3


def test_a_finished_run_stops_and_never_asks_the_broker(run, monkeypatch):
    bid, stored = run
    stored.results.end_date = datetime(2020, 1, 1)
    calls = _provider(monkeypatch, lambda *a: _bars("2020-01-01", 1))
    assert client.post(f"/api/backtests/{bid}/live-refresh").json()["live"] is False
    assert calls == []


def test_demo_data_is_never_live(run, monkeypatch):
    bid, stored = run
    stored.data_source = "synthetic"
    calls = _provider(monkeypatch, lambda *a: _bars("2020-01-01", 1))
    assert client.post(f"/api/backtests/{bid}/live-refresh").json()["live"] is False
    assert calls == []


def test_bars_outside_the_session_are_not_added(run, monkeypatch):
    bid, stored = run
    last = stored.results.price_data.index[-1]
    stored.session_start, stored.session_end = last.time(), (last + timedelta(minutes=1)).time()
    _provider(monkeypatch, lambda *a: _bars(last, 5))
    assert len(client.post(f"/api/backtests/{bid}/live-refresh").json()["bars"]) == 3


def test_an_unknown_run_is_a_404():
    assert client.post("/api/backtests/nope/live-refresh").status_code == 404


# ── from the stream hub (upgrade plan, Feature 3) ───────────────────────────

def test_with_the_stream_up_bars_come_from_it_and_schwab_is_not_asked(run, monkeypatch):
    bid, stored = run
    last = stored.results.price_data.index[-1]
    streamed = _bars(last, 3)
    streamed.loc[last, "close"] = 77.0
    monkeypatch.setattr(backtests.stream_hub, "bars_1m", lambda root, since: streamed)
    calls = _provider(monkeypatch, lambda *a: _bars(last, 1))
    body = client.post(f"/api/backtests/{bid}/live-refresh").json()
    assert calls == []
    assert body["stream"] is True and body["live"] is True
    assert len(body["bars"]) == 5 and body["bars"][2]["c"] == 77.0


def test_streamed_minutes_are_built_up_to_the_runs_timeframe(run, monkeypatch):
    bid, stored = run
    stored.results.timeframe = "5m"
    last = pd.Timestamp(datetime.now().replace(second=0, microsecond=0)).floor("5min") - pd.Timedelta(minutes=5)
    stored.results.price_data = _bars(last - pd.Timedelta(minutes=10), 3).set_axis(
        pd.date_range(last - pd.Timedelta(minutes=10), periods=3, freq="5min"))
    monkeypatch.setattr(backtests.stream_hub, "bars_1m", lambda root, since: _bars(since, 7))
    _provider(monkeypatch, lambda *a: _bars(last, 1))
    body = client.post(f"/api/backtests/{bid}/live-refresh").json()
    assert body["stream"] is True
    assert [b["t"][11:16] for b in body["bars"]][-2:] == [last.strftime("%H:%M"), (last + pd.Timedelta(minutes=5)).strftime("%H:%M")]
    assert body["bars"][-2]["v"] == 25.0          # five 1-minute bars of 5


def test_without_the_stream_it_polls_schwab_as_before(run, monkeypatch):
    bid, stored = run
    monkeypatch.setattr(backtests.stream_hub, "bars_1m", lambda root, since: None)
    calls = _provider(monkeypatch, lambda *a: _bars(stored.results.price_data.index[-1], 2))
    body = client.post(f"/api/backtests/{bid}/live-refresh").json()
    assert len(calls) == 1 and body["stream"] is False


def test_daily_charts_never_use_the_stream(run, monkeypatch):
    bid, stored = run
    stored.results.timeframe = "1d"
    asked = []
    monkeypatch.setattr(backtests.stream_hub, "bars_1m", lambda root, since: asked.append(1))
    _provider(monkeypatch, lambda *a: _bars("2020-01-01", 0))
    assert client.post(f"/api/backtests/{bid}/live-refresh").json()["stream"] is False
    assert asked == []
