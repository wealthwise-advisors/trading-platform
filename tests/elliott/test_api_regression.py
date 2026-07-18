"""API regression tests (Task 7, requirement 6) -- in-process via FastAPI's
TestClient, no live uvicorn server required, so this suite is fully
self-contained and safe to run in CI. Exercises the exact endpoints the
React frontend and HTML report export depend on: run a backtest, fetch its
Elliott Wave analysis, export its HTML report.
"""
from conftest import assert_deterministic

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_BACKTEST_BODY = {
    "symbol": "ES",
    "strategy_id": "ma_crossover",
    "timeframe": "1h",
    "data_source": "synthetic",
    "start_date": "2023-01-01",
    "end_date": "2023-06-01",
    "params": {"fast": 9, "slow": 21},
}


def _run_backtest() -> str:
    resp = client.post("/api/backtests", json=_BACKTEST_BODY)
    assert resp.status_code == 200, resp.text
    return resp.json()["backtest_id"]


def test_backtest_endpoint_runs_successfully():
    resp = client.post("/api/backtests", json=_BACKTEST_BODY)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "backtest_id" in body
    assert body["symbol"] == "ES"
    assert body["data_points"] > 0


def test_elliott_wave_endpoint_returns_valid_structure():
    backtest_id = _run_backtest()
    resp = client.get(f"/api/backtests/{backtest_id}/elliott-wave")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "primary" in body and "minor" in body
    for degree in ("primary", "minor"):
        assert "n_swings" in body[degree]
        assert "wave_sequence" in body[degree]
        assert "warnings" in body[degree]
        assert isinstance(body[degree]["wave_sequence"], list)
        for w in body[degree]["wave_sequence"]:
            assert "t" in w and "price" in w and "wave" in w and "kind" in w


def test_elliott_wave_endpoint_unknown_backtest_id_404s():
    resp = client.get("/api/backtests/AT-does-not-exist/elliott-wave")
    assert resp.status_code == 404


def test_report_export_endpoint_returns_html():
    backtest_id = _run_backtest()
    resp = client.get(f"/api/backtests/{backtest_id}/report")
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 10_000, "HTML report suspiciously small -- likely a broken render"
    assert b"<html" in resp.content.lower()


def test_elliott_wave_endpoint_deterministic_across_repeated_requests():
    """Same backtest, fetched twice -- the analysis must not silently
    change between requests (e.g. from stray global/cache state)."""
    backtest_id = _run_backtest()

    def fetch():
        resp = client.get(f"/api/backtests/{backtest_id}/elliott-wave")
        body = resp.json()
        return tuple(
            tuple((w["wave"], round(w["price"], 6), w["t"]) for w in body[degree]["wave_sequence"])
            for degree in ("primary", "minor")
        )

    assert_deterministic(fetch, runs=3)
