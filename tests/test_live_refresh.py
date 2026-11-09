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
