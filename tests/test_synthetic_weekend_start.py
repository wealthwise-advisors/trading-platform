"""Demo (synthetic) data always opens at 09:30 on a weekday.

Reported 2026-10-27 as the Chart page's 1m button "doing nothing": selecting
1m moved the range to Sun 25 - Mon 26 Oct. The generator skips weekend days
but keeps its clock running, so the bars began at MONDAY 00:00 (390 of them,
00:00-06:29) and the 09:30-16:00 session filtered every one out -- the run
failed and the chart stayed on 5m. Market Grid's demo data had the same
weakness. Both now start at 09:30 on the first weekday of the range.
"""

from datetime import date, datetime

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from api.routers.backtests import synthetic_start

client = TestClient(app)


def test_a_weekend_start_moves_to_monday_0930():
    assert synthetic_start(date(2026, 10, 25)) == datetime(2026, 10, 26, 9, 30)   # Sunday
    assert synthetic_start(date(2026, 10, 24)) == datetime(2026, 10, 26, 9, 30)   # Saturday


def test_a_weekday_start_is_that_day_at_0930():
    assert synthetic_start(date(2026, 10, 23)) == datetime(2026, 10, 23, 9, 30)   # Friday


def test_a_1m_backtest_over_a_weekend_start_runs_in_the_regular_session():
    r = client.post("/api/backtests", json={
        "symbol": "ES", "timeframe": "1m", "data_source": "synthetic",
        "strategy_id": "rsi_divergence",
        "params": {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5},
        "start_date": "2026-10-25", "end_date": "2026-10-26",
        "session_start": "09:30:00", "session_end": "16:00:00",
    })
    assert r.status_code == 200, r.text[:300]
    bars = client.get(f"/api/backtests/{r.json()['backtest_id']}/price-data").json()["bars"]
    first = pd.Timestamp(bars[0]["t"])
    assert first == pd.Timestamp("2026-10-26 09:30")


def test_market_grid_demo_over_a_weekend_start_runs_too():
    r = client.post("/api/replay", json={
        "symbol": "ES", "timeframes": ["1m", "5m"], "data_source": "synthetic",
        "strategy_id": "rsi_divergence",
        "start_date": "2026-10-25", "end_date": "2026-10-26",
    })
    assert r.status_code == 200, r.text[:300]
    assert r.json()["total_bars"] > 0
