"""
The one place OHLCV bars get aggregated up a timeframe.

WHY THIS MODULE EXISTS SEPARATELY

There used to be three of these. `MultiReplaySession` had one, ExternalCSVProvider
had one, and SchwabDataProvider had a bare `df.resample(...)` inline in `load()`.
Two of them were fixed to anchor on the session open; the third was not, and
nothing pointed that out because each path had its own copy. The result was that
the SAME bar, on the SAME date, in the SAME session, came out differently
depending on which code path reached it:

    session 09:30-16:00, first bar of the session
        timeframe   provider path      session-anchored
        20m         09:40              09:30
        25m         09:35              09:30
        35m         09:55              09:30
        40m         10:00              09:30
        45m         09:45              09:30
        1h          10:00              09:30

and worse, on which OTHER timeframes were selected -- the replay picks its source
resolution from the whole selection, so adding 5m to a 1h pane changed that 1h
pane's VWAP by 0.72 points on a bar that had closed hours earlier.

So there is now exactly one implementation and every caller uses it. A fourth
copy appearing anywhere is the bug, not the anchoring.

WHY THE ANCHOR MATTERS

pandas anchors bins at MIDNIGHT by default (origin="start_day"). A bar size that
does not divide the session open's offset from midnight lands off the session
grid, and every bar of that session is shifted:

    session 18:00 -> 1080 minutes past midnight
        1080 % 25 = 5    25m bars sit 5 minutes off the session grid
        1080 % 35 = 30   35m likewise
    session 09:30 -> 570 minutes
        570 % 20, 25, 35, 40, 45, 60 are all non-zero -- six of the eleven
        timeframes are wrong, including 1h

Which timeframes break depends on the anchor, which is why this first surfaced as
"only 25m looks wrong" on a Globex session: 25m and 35m are the only two that
miss an 18:00 grid. It was never specific to 25m, and patching it per timeframe
is what kept the regressions coming.
"""

from __future__ import annotations

from datetime import time as dt_time

import pandas as pd

# Minutes per supported timeframe label, and the pandas resample alias.
TF_MINUTES: dict[str, int] = {
    "1m": 1, "2m": 2, "5m": 5, "10m": 10, "15m": 15, "20m": 20, "25m": 25,
    "30m": 30, "35m": 35, "40m": 40, "45m": 45, "1h": 60,
}
TF_ALIAS: dict[str, str] = {
    "1m": "1min", "2m": "2min", "5m": "5min", "10m": "10min", "15m": "15min",
    "20m": "20min", "25m": "25min", "30m": "30min", "35m": "35min",
    "40m": "40min", "45m": "45min", "1h": "1h",
}

OHLCV_AGG = {"open": "first", "high": "max", "low": "min",
             "close": "last", "volume": "sum"}


def session_origin(first_ts, session_start):
    """
    The bin origin: the most recent session open at or before `first_ts`.

    Returns None when there is no session anchor, which leaves pandas on its
    default and groups by calendar day -- correct for a 24-hour chart.
    """
    if session_start is None:
        return None
    day = pd.Timestamp(first_ts).normalize()
    origin = day + pd.Timedelta(hours=session_start.hour,
                                minutes=session_start.minute,
                                seconds=getattr(session_start, "second", 0))
    if origin > pd.Timestamp(first_ts):
        origin -= pd.Timedelta(days=1)
    return origin


#: Name of the optional column carrying each output bar's own volume-weighted
#: price. Kept out of OHLCV_AGG so it is only ever produced on request -- the
#: CSV export and every provider return plain OHLCV.
VWAP_PRICE = "vwap_price"


# WHERE BARS START TILING -- and why it is NOT the session open.
#
# Two anchors are involved and they are not the same one:
#
#     bars  tile from midnight in the EXCHANGE's timezone
#     VWAP  resets at the SESSION open
#
# This code used the session open for both, which is right for any timeframe
# that divides the gap between them and wrong for the rest. The Globex open is
# 17:00 CT, i.e. 1020 minutes after exchange midnight:
#
#     5m 10m 15m 20m 30m 1h   1020 divides evenly   -> same grid either way
#     25m  1020/25 = 40.8     -> grids differ
#     35m  1020/35 = 29.14    -> grids differ
#     40m  1020/40 = 25.5     -> grids differ
#     45m  1020/45 = 22.67    -> grids differ
#
# Which is exactly why 30m matched the reference platform perfectly for days
# while 45m did not, and why fixing it one timeframe at a time never converged.
#
# Settled against the reference on /ES 45m, 2026-08-13. Its bar opens 12:45 CT;
# 765 / 45 = 17 exactly from exchange midnight. Only that window reproduces its
# OHLC -- O 7810.50 H 7816.25 L 7810.50 C 7814.50, range 5.75. The session-open
# grid gives 12:30 CT and a range of 6.25.
#
# Timestamps in this app are Eastern, so a Central exchange sits at 01:00 ET.
_EXCHANGE_TZ_OFFSET_FROM_ET = {
    "CME": -1, "CBOT": -1, "NYMEX": -1, "COMEX": -1,   # Chicago / New York desks, CT clock
    "NYSE": 0, "NASDAQ": 0, "ARCA": 0, "BATS": 0,      # already Eastern
}

_SYMBOL_EXCHANGE = {
    "ES": "CME", "MES": "CME", "NQ": "CME", "MNQ": "CME",
    "RTY": "CME", "MRY": "CME", "M2K": "CME",
    "YM": "CBOT", "MYM": "CBOT", "ZN": "CBOT", "ZB": "CBOT",
    "ZF": "CBOT", "ZT": "CBOT", "ZC": "CBOT", "ZS": "CBOT", "ZW": "CBOT",
    "CL": "NYMEX", "MCL": "NYMEX", "NG": "NYMEX", "RB": "NYMEX", "HO": "NYMEX",
    "GC": "COMEX", "MGC": "COMEX", "SI": "COMEX", "SIL": "COMEX", "HG": "COMEX",
}


def bar_anchor(symbol: str | None) -> dt_time:
    """
    The wall-clock time, in the data's Eastern timestamps, at which each day's
    bar grid starts.

    01:00 for anything trading on a Central-time exchange -- every CME/CBOT/
    NYMEX/COMEX future -- because their day begins at midnight Chicago.
    00:00 for US equities, which are already on the Eastern clock, and for
    anything unrecognised: that is the plain calendar-day grid and the safer
    default for an instrument whose exchange we do not know.
    """
    hours = _EXCHANGE_TZ_OFFSET_FROM_ET.get(
        _SYMBOL_EXCHANGE.get((symbol or "").upper(), ""), 0)
    return dt_time(hour=(-hours) % 24)


def _vwap_price(chunk: pd.DataFrame) -> float:
    """
    One bar's own volume-weighted price, from the finer bars inside it.

    This is the figure a broker platform's VWAP study accumulates -- thinkorswim's
    vwap() fundamental, which it derives from ticks. We have no ticks; minute bars
    are the finest this feed carries, so each minute contributes a price weighted
    by its volume, and the question is which price.

    (H+L)/2, not the textbook (H+L+C)/3. Fitted against four bars the reference
    platform printed (/ES 2026-08-13, 1h/45m/30m/20m), twenty band fields in all:

        per-minute price     total error   bars with every whole number matching
        (H+L)/2                   0.9159   4 of 4
        (H+L+C)/3                 1.3814   3 of 4
        (O+H+L+C)/4               1.6021   3 of 4
        close                     2.6124   2 of 4

    It improves every bar individually, not just the total -- VWAP error goes
    0.048 -> 0.018 on 1h, 0.118 -> 0.089 on 45m, 0.038 -> 0.009 on 30m and
    0.043 -> 0.013 on 20m -- which is what distinguishes a better estimator from
    a lucky fit. It is also the more sensible one on its face: (H+L+C)/3 counts
    the close twice over and so leans toward wherever the minute happened to
    finish, while the true volume-weighted price of trades inside a minute sits
    nearer the middle of its range.

    Still an approximation of a tick figure from bar data, and still fitted to
    four bars. tests/test_reference_platform_parity.py holds it to them.

    Degenerate cases fall back to the plain mean of that price, which is what the
    weighted mean collapses to when there is one source row or no volume.
    """
    vol = chunk["volume"].astype("float64") if "volume" in chunk else None
    price = (chunk["high"].astype("float64") + chunk["low"].astype("float64")) / 2.0
    if vol is None or not vol.sum() > 0:
        return float(price.mean())
    return float((price * vol).sum() / vol.sum())


def resample_ohlcv(df: pd.DataFrame, timeframe: str, session_start=None,
                   with_vwap_price: bool = False) -> pd.DataFrame:
    """
    Aggregate a finer OHLCV frame up to `timeframe`, anchored on the session.

    Bins RESTART at every session open. One origin for the whole frame is not
    enough: an 18:00-17:00 session is 1380 minutes, and 1380 % 25, 35, 40 and 45
    are all non-zero, so each following session would start a few minutes further
    off the grid than the last. Grouping first is the same grouping
    calc_vwap_bands uses for its daily reset, so a bar and its VWAP always agree
    about which session they belong to.

    `session_start=None` keeps the plain calendar-day behaviour, which is what a
    24-hour chart wants.
    """
    if timeframe not in TF_ALIAS:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; expected one of {list(TF_ALIAS)}")
    agg = {k: v for k, v in OHLCV_AGG.items() if k in df.columns}
    alias = TF_ALIAS[timeframe]

    def finish(grouper, out):
        """Attach the per-bar volume-weighted price, if it was asked for."""
        out = out.dropna(subset=["open"])
        if not with_vwap_price or out.empty:
            return out
        out[VWAP_PRICE] = grouper.apply(_vwap_price).reindex(out.index)
        return out

    if session_start is None or df.empty:
        grouper = df.resample(alias, closed="left", label="left")
        return finish(grouper, grouper.agg(agg))

    anchor = pd.Timedelta(hours=session_start.hour, minutes=session_start.minute,
                          seconds=getattr(session_start, "second", 0))
    session_id = (df.index - anchor).normalize()
    pieces = []
    for sid, chunk in df.groupby(session_id, sort=True):
        grouper = chunk.resample(alias, closed="left", label="left",
                                 origin=pd.Timestamp(sid) + anchor)
        pieces.append(finish(grouper, grouper.agg(agg)))
    if not pieces:
        return df.iloc[0:0]
    return pd.concat(pieces).sort_index()
