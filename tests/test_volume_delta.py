"""Volume Delta and Cumulative Volume Delta, as sir defined them (email, 2026-11-26).

    Delta   = Ask Vol - Bid Vol           (one candle)
    Delta % = Delta / Total Volume x 100  (his > 60% filter)
    CVD     = CVD[t-1] + Delta[t], restarting each session:
              6 PM - midnight, midnight - 8 AM, 8 AM onward (Eastern)

Schwab sells one-minute bars, not trades, so Ask Vol / Bid Vol are estimated
with sir's own buyers/sellers split (calc_volume_split): where the candle
closed inside its range.
"""

import pandas as pd
import pytest

from api import serializers
from src.analysis.indicators import calc_cvd, calc_volume_delta, calc_volume_split


def _bars(rows, start="2026-11-24 09:30", freq="1min"):
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    return pd.DataFrame(rows, columns=["high", "low", "close", "volume"], index=idx)


def test_delta_is_buyers_minus_sellers_and_percent_of_volume():
    # Sir's example: 820 at the ask, 180 at the bid, 1,000 in all -> +640, +64.0 %.
    df = _bars([(10.0, 0.0, 8.2, 1000.0)])
    delta, pct = calc_volume_delta(df["high"], df["low"], df["close"], df["volume"])
    assert delta.iloc[0] == 640 and pct.iloc[0] == pytest.approx(64.0)
    _, buyers, sellers = calc_volume_split(df["high"], df["low"], df["close"], df["volume"])
    assert delta.iloc[0] == buyers.iloc[0] - sellers.iloc[0]


def test_no_volume_and_no_range_give_zero_not_errors():
    df = _bars([(10.0, 10.0, 10.0, 500.0), (11.0, 9.0, 10.0, 0.0)])
    delta, pct = calc_volume_delta(df["high"], df["low"], df["close"], df["volume"])
    assert list(delta) == [0, 0] and list(pct) == [0, 0]


def test_cvd_is_the_running_total_of_sirs_example():
    # Pullback -600, support hold -400, breakout +850 -> CVD -600, -1,000, -150.
    d = pd.Series([-600.0, -400.0, 850.0], index=pd.date_range("2026-11-24 09:30", periods=3, freq="1min"))
    assert list(calc_cvd(d)) == [-600, -1000, -150]


@pytest.mark.parametrize("before,at", [("17:59", "18:00"), ("23:59", "00:00"), ("07:59", "08:00")])
def test_cvd_restarts_at_each_of_the_three_sessions(before, at):
    day = "2026-11-24" if at != "00:00" else "2026-11-23"
    t0 = pd.Timestamp(f"{day} {before}")
    idx = pd.DatetimeIndex([t0 - pd.Timedelta(minutes=1), t0, t0 + pd.Timedelta(minutes=1)])
    cvd = calc_cvd(pd.Series([100.0, 50.0, 30.0], index=idx))
    assert list(cvd) == [100, 150, 30]            # the third bar opens a new session


def test_the_hour_after_four_stays_in_the_day_session():
    # 4-5 PM ET still trades; nothing restarts until the 6 PM open.
    idx = pd.date_range("2026-11-24 15:59", periods=3, freq="1h")      # 15:59, 16:59, 17:59
    assert list(calc_cvd(pd.Series([1.0, 2.0, 3.0], index=idx))) == [1, 3, 6]


def test_chart_series_carry_delta_percent_and_cvd():
    df = _bars([(10.0, 0.0, 8.2, 1000.0), (10.0, 0.0, 1.0, 500.0), (10.0, 0.0, 5.0, 200.0)])
    df["open"] = df["close"]
    ind = serializers.price_data_to_response(df)["indicators"]
    assert ind["delta"] == [640, -400, 0]
    assert ind["delta_pct"] == [64.0, -80.0, 0.0]
    assert ind["cvd"] == [640, 240, 240]
