"""POC Average at a moment, for flagging swings on the Chart page (2026-10-27).

At a swing point, sir wants to know whether any timeframe's POC sits on the
POC Average of the selected timeframes -- the same whole number, the rule POC
Match uses. These tests pin the three things that number depends on, each
the way Market Grid computes it, so the Chart page and Market Grid can never
disagree:

  * which bars count -- only bars CLOSED by the moment;
  * which days count -- each timeframe's own specified calendar days, counted
    back from its last closed bar (web/src/lib/profileWindow.ts);
  * the average -- sum of the timeframes' POCs / how many have one.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis.indicators import calc_volume_profile
from src.analysis.poc_average import TF_DAYS, poc_average_at, profile_window

ROOT = Path(__file__).resolve().parents[1]


def _pane(start: str, periods: int, minutes: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    mid = 5000 + np.cumsum(rng.normal(0, 1.5, periods))
    idx = pd.date_range(start, periods=periods, freq=f"{minutes}min")
    return pd.DataFrame({"high": mid + rng.uniform(0.25, 3, periods),
                         "low": mid - rng.uniform(0.25, 3, periods),
                         "volume": rng.integers(50, 5000, periods).astype(float)}, index=idx)


def test_day_table_matches_market_grid():
    """The backend's day counts are the frontend's SPECIFIED table, entry for entry."""
    ts = (ROOT / "web/src/lib/chartSetup.ts").read_text(encoding="utf-8")
    block = ts[ts.index("const SPECIFIED"):]
    block = block[:block.index("\n}\n")]
    specified = {tf: int(n) for tf, n in re.findall(r'"(\d+[mh])":\s*(\d+)', block)}
    assert specified, "could not read SPECIFIED from chartSetup.ts"
    assert TF_DAYS == specified


def test_window_counts_own_calendar_days_back_from_last_closed_bar():
    df = _pane("2026-10-20 00:00", 4 * 24 * 12, 5, seed=1)       # 20..23 Oct, 5m
    moment = pd.Timestamp("2026-10-23 12:00")
    w = profile_window(df, "5m", moment)                          # 5m = 2 D
    assert w.index.min() == pd.Timestamp("2026-10-22 00:00")
    # Closed by 12:00 means opened by 11:55.
    assert w.index.max() == pd.Timestamp("2026-10-23 11:55")


def test_a_bar_still_forming_at_the_moment_is_left_out():
    df = _pane("2026-10-23 09:00", 4, 60, seed=2)                 # 09:00..12:00, 1h
    w = profile_window(df, "1h", pd.Timestamp("2026-10-23 11:30"))
    assert list(w.index.hour) == [9, 10]                           # 11:00 bar closes 12:00


def test_timeframe_without_a_day_count_keeps_everything_loaded():
    df = _pane("2026-10-01 00:00", 30 * 24 * 4, 15, seed=3)
    w = profile_window(df, "25m", pd.Timestamp("2026-10-30 23:59"))
    assert w.index.min() == df.index.min()


def test_average_is_the_mean_of_each_timeframes_poc_and_matches_by_whole_number():
    panes = {
        "5m": _pane("2026-10-20 00:00", 4 * 24 * 12, 5, seed=4),
        "15m": _pane("2026-10-20 00:00", 4 * 24 * 4, 15, seed=5),
        "1h": _pane("2026-10-20 00:00", 4 * 24, 60, seed=6),
    }
    moment = pd.Timestamp("2026-10-23 15:00")
    [got] = poc_average_at(panes, [moment])

    # Independent recompute, window by hand.
    want = {}
    for tf, df in panes.items():
        minutes = {"5m": 5, "15m": 15, "1h": 60}[tf]
        closed = df[df.index + pd.Timedelta(minutes=minutes) <= moment]
        first_day = (closed.index.max().normalize() - pd.Timedelta(days=TF_DAYS[tf] - 1))
        win = closed[closed.index >= first_day]
        want[tf] = calc_volume_profile(win["high"], win["low"], win["high"], win["volume"])["poc"]
    avg = sum(want.values()) / len(want)

    assert got["pocs"] == pytest.approx(want)
    assert got["average"] == pytest.approx(avg)
    assert got["matches"] == [tf for tf, p in want.items() if int(p) == int(avg)]


def test_a_timeframe_with_no_closed_bars_is_left_out_of_the_sum_and_the_count():
    panes = {
        "5m": _pane("2026-10-23 09:00", 48, 5, seed=7),
        "1h": _pane("2026-10-23 14:00", 3, 60, seed=8),           # nothing closed by 10:00
    }
    [got] = poc_average_at(panes, [pd.Timestamp("2026-10-23 10:00")])
    assert set(got["pocs"]) == {"5m"}
    assert got["average"] == pytest.approx(got["pocs"]["5m"])
    assert got["matches"] == ["5m"]


def test_no_bars_anywhere_gives_no_average_and_no_matches():
    panes = {"5m": _pane("2026-10-23 12:00", 5, 5, seed=9)}
    [got] = poc_average_at(panes, [pd.Timestamp("2026-10-23 09:00")])
    assert got["average"] is None and got["matches"] == [] and got["pocs"] == {}
