"""
Every timeframe the UI offers must work on every endpoint that takes one.

The Backtest form, the Market Grid and (now) the Export page all offer the
timeframes in web/src/lib/chartSetup.ts -- thirteen since 2h and 4h were added. The synthetic data path in
api/routers/backtests.py::_build_provider carried its own five-entry minutes
table, so 2m, 10m, 20m, 25m, 35m and 45m raised a KeyError there. That escaped
as a bare 500 "Internal Server Error" -- no hint which input was wrong -- and
because the Optimizer and the data export call the same function, all three
endpoints failed the same way. Synthetic is the default data source, so this
was reachable from a fresh page by changing one dropdown.

The list below is the UI's list, restated rather than imported: this suite is
the contract that the backend keeps up with the frontend, and importing the
backend's own table would make it pass by definition.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

UI_TIMEFRAMES = ["1m", "2m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h", "2h", "4h"]

#: The six that used to fail.
FORMERLY_BROKEN = ["2m", "10m", "20m", "25m", "35m", "45m"]

_PARAMS = {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5}
_RANGE = {"start_date": "2026-01-05", "end_date": "2026-01-09"}


def _backtest_body(tf: str) -> dict:
    return {"symbol": "ES", "timeframe": tf, "data_source": "synthetic",
            "strategy_id": "rsi_divergence", "params": _PARAMS, **_RANGE}


class TestSyntheticBacktest:
    @pytest.mark.parametrize("tf", UI_TIMEFRAMES)
    def test_every_offered_timeframe_runs(self, tf):
        r = client.post("/api/backtests", json=_backtest_body(tf))
        assert r.status_code == 200, f"{tf}: {r.status_code} {r.text[:200]}"

    def test_an_unknown_timeframe_is_a_400_that_names_the_input(self):
        r = client.post("/api/backtests", json=_backtest_body("7m"))
        assert r.status_code == 400, f"got {r.status_code}: {r.text[:200]}"
        detail = r.json()["detail"]
        assert "7m" in detail
        assert "Supported" in detail


class TestSyntheticOptimizer:
    @pytest.mark.parametrize("tf", FORMERLY_BROKEN)
    def test_the_formerly_broken_timeframes_run(self, tf):
        body = {"symbol": "ES", "timeframe": tf, "data_source": "synthetic",
                "strategy_id": "rsi_divergence", **_RANGE}
        r = client.post("/api/optimize", json=body)
        assert r.status_code == 200, f"{tf}: {r.status_code} {r.text[:200]}"


class TestSyntheticExport:
    @pytest.mark.parametrize("tf", UI_TIMEFRAMES)
    def test_every_offered_timeframe_exports(self, tf):
        r = client.get("/api/data/export", params={
            "symbol": "ES", "timeframe": tf, "data_source": "synthetic",
            "start": _RANGE["start_date"], "end": _RANGE["end_date"], "format": "csv",
        })
        assert r.status_code == 200, f"{tf}: {r.status_code} {r.text[:200]}"
        assert r.content, f"{tf}: empty export"
