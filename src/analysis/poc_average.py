"""POC Average at a moment -- the Market Grid number, for flagging swings.

Sir's rule (2026-10-27): at a swing point, if any selected timeframe's POC has
the same whole number as the POC Average of all of them, flag that swing on
the Chart page.

Everything here mirrors how Market Grid computes the same number in the
browser, so the two pages cannot disagree:

  * only bars CLOSED by the moment count (web/src/lib/pocColumns.barsClosedBy);
  * each timeframe profiles its OWN specified calendar days, counted back from
    its last closed bar (web/src/lib/profileWindow.ts); a timeframe with no
    day count keeps everything loaded;
  * the profile is calc_volume_profile -- the function the browser's
    computeVolumeProfile was verified against;
  * the average is the sum of the POCs / how many timeframes have one, and a
    match is the same whole number (truncation, as POC Match uses).
"""

from __future__ import annotations

import math

import pandas as pd

from src.analysis.indicators import calc_volume_profile
from src.data.resample import TF_MINUTES

# Each timeframe's specified days -- the SPECIFIED table in
# web/src/lib/chartSetup.ts. tests/test_poc_average.py fails if they drift.
# 3m, 25m and 35m deliberately have none.
TF_DAYS: dict[str, int] = {
    "1m": 2, "5m": 2, "10m": 3, "15m": 4, "20m": 5,
    "30m": 15, "45m": 20, "1h": 25, "2h": 180, "4h": 180,
}


def profile_window(df: pd.DataFrame, timeframe: str, moment: pd.Timestamp) -> pd.DataFrame:
    """The bars `timeframe`'s profile is built from at `moment`.

    `df` is indexed by bar OPEN time. A bar counts once it has closed
    (open + length <= moment). Of those, keep the last TF_DAYS[timeframe]
    calendar days, inclusive, ending on the last closed bar's date.
    """
    closed = df[df.index + pd.Timedelta(minutes=TF_MINUTES[timeframe]) <= moment]
    days = TF_DAYS.get(timeframe)
    if closed.empty or days is None:
        return closed
    first_day = closed.index.max().normalize() - pd.Timedelta(days=days - 1)
    return closed[closed.index >= first_day]


def poc_average_at(
    panes: dict[str, pd.DataFrame],
    moments: list[pd.Timestamp],
    bins: int = 48,
    value_area: float = 0.70,
) -> list[dict]:
    """For each moment: every timeframe's POC, their average, and which match it.

    `panes` maps timeframe -> bars (high, low, volume), indexed by open time.
    A timeframe with no closed bars yet, or no volume, has no POC and is left
    out of both the sum and the count.
    """
    out = []
    for moment in moments:
        pocs: dict[str, float] = {}
        for tf, df in panes.items():
            win = profile_window(df, tf, moment)
            if len(win) < 2:
                continue
            vp = calc_volume_profile(win["high"], win["low"], win["high"],
                                     win["volume"], bins=bins, value_area_pct=value_area)
            if vp["poc"] is not None and math.isfinite(vp["poc"]):
                pocs[tf] = float(vp["poc"])
        average = sum(pocs.values()) / len(pocs) if pocs else None
        matches = ([tf for tf, p in pocs.items() if math.trunc(p) == math.trunc(average)]
                   if average is not None else [])
        out.append({"t": moment.isoformat(), "average": average, "pocs": pocs, "matches": matches})
    return out
