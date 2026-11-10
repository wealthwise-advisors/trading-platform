"""The chart's Compare overlay: a second symbol over the run's own bars."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _run():
    r = client.post("/api/backtests", json={
        "symbol": "ES", "timeframe": "5m", "data_source": "synthetic", "strategy_id": "rsi_divergence",
        "params": {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5},
        "start_date": "2026-11-06", "end_date": "2026-11-06",
        "session_start": "09:30:00", "session_end": "16:00:00",
    })
    assert r.status_code == 200, r.text[:300]
    return r.json()["backtest_id"]


def test_another_symbol_comes_back_over_the_same_session():
    bid = _run()
    body = client.get(f"/api/backtests/{bid}/compare", params={"symbol": "nq"}).json()
    assert body["symbol"] == "NQ"
    assert body["t"] and len(body["t"]) == len(body["c"])
    assert all("09:30" <= t[11:16] < "16:00" for t in body["t"])


def test_a_symbol_is_required():
    bid = _run()
    assert client.get(f"/api/backtests/{bid}/compare").status_code == 422


def test_an_unknown_run_is_a_404():
    assert client.get("/api/backtests/nope/compare", params={"symbol": "NQ"}).status_code == 404
