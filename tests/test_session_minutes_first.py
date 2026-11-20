"""
Backtest session hours cut the MINUTES, then build the candles -- as the Market Grid does.

Cutting finished candles by their open time dropped the 9:00 1h/2h/4h candle under
RTH (it opens before 9:30), and with it the real 9:30-10:00 trading (2026-11-20).
"""

from datetime import datetime, time

import numpy as np
import pandas as pd
import pytest

from src.backtesting.engine import BacktestEngine
from src.strategies.ma_crossover import MACrossoverStrategy


class _Minutes:
    """Two days of /ES 1m bars around the clock; refuses anything but 1m."""

    def __init__(self):
        idx = pd.date_range("2026-11-16 00:00", "2026-11-17 23:59", freq="1min")
        price = 6000 + np.arange(len(idx)) * 0.25
        self.df = pd.DataFrame({"open": price, "high": price + 1, "low": price - 1,
                                "close": price + 0.25, "volume": 10.0}, index=idx)

    def load(self, symbol, start, end, timeframe="1m"):
        assert timeframe == "1m", timeframe
        return self.df.loc[start:end]


def _run(tf):
    engine = BacktestEngine(data_provider=_Minutes(), strategy=MACrossoverStrategy(fast=2, slow=3),
                            symbol="ES", timeframe=tf, tick_size=0.25, tick_value=12.5,
                            point_value=50.0, session_start=time(9, 30), session_end=time(16, 0))
    return engine.run(datetime(2026, 11, 16), datetime(2026, 11, 17, 23, 59)).price_data


@pytest.mark.parametrize("tf, opens", [
    ("1h", ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]),
    ("2h", ["09:00", "11:00", "13:00", "15:00"]),
    ("4h", ["09:00", "13:00"]),
])
def test_rth_keeps_the_candle_holding_the_open(tf, opens):
    day = _run(tf).loc["2026-11-16"]
    assert [t.strftime("%H:%M") for t in day.index] == opens
    first = day.iloc[0]
    # Built from 9:30 onward only: the pre-market minutes are not in it.
    assert first["open"] == _Minutes().df.loc["2026-11-16 09:30", "open"]
    # Each day's volume is exactly the 390 RTH minutes.
    assert day["volume"].sum() == 390 * 10.0


def test_rth_on_30m_is_unchanged():
    day = _run("30m").loc["2026-11-16"]
    assert day.index[0].strftime("%H:%M") == "09:30" and len(day) == 13
