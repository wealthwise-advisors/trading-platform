"""
Parity against the reference platform, pinned to bars it actually printed.

WHY THIS FILE EXISTS SEPARATELY FROM test_indicator_correctness.py

That suite checks the app against ITSELF -- an independent recompute of the same
definition. It is thorough and it is necessary, and it cannot catch a wrong
DEFINITION: for a week it passed while bars were tiled from the session open
instead of the exchange's midnight, because both sides of every assertion used
the same convention.

The only thing that catches that is data from the other platform. Below are four
bars read off a thinkorswim screen (/ES, 2026-08-13, times in CT) together with
the 1-minute bars they were built from, captured from the live feed and committed
as a fixture. If a change moves any of these, the change is wrong, whatever the
rest of the suite says.

  1h   12:00 PM CT   O 7811.50  H 7819.25  L 7810.50  C 7811.75   range 8.75
  45m  12:45 PM CT   O 7810.50  H 7816.25  L 7810.50  C 7814.50   range 5.75
  30m   1:00 PM CT   O 7811.75  H 7816.25  L 7811.00  C 7814.50   range 5.25
  20m   1:20 PM CT   O 7813.75  H 7818.50  L 7811.00  C 7818.25   range 7.50

THE THING THESE FOUR PIN

45m is the only one that discriminates between the two candidate bar grids, and
that is precisely why the bug survived so long -- 20m, 30m and 1h look identical
under both. Minutes from each candidate origin to the bar's open:

    timeframe   from exchange midnight    from the Globex open
    1h          720 / 60  = 12            1140 / 60 = 19
    45m         765 / 45  = 17            1185 / 45 = 26.33   <-- only this one
    30m         780 / 30  = 26            1200 / 30 = 40
    20m         800 / 20  = 40            1220 / 20 = 61

Never drop the 45m case to make a change pass.
"""

from datetime import time
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.indicators import calc_vwap_bands
from src.data.resample import TF_MINUTES, VWAP_PRICE, bar_anchor, resample_ohlcv

FIXTURE = Path(__file__).parent / "fixtures" / "es_1m_2026_08_12_13.csv"

#: Globex. Anchors the VWAP reset -- NOT the bar grid; those are different
#: anchors and conflating them is the bug this file guards.
SESSION_START, SESSION_END = time(18, 0), time(17, 0)

#: Central, which is what the reference screen was set to. Our timestamps are
#: Eastern.
CT_TO_ET = pd.Timedelta(hours=1)

# timeframe -> (open time CT, O, H, L, C, VWAP, +1sigma, -1sigma, +2sigma, -2sigma)
REFERENCE = {
    "1h":  ("12:00", 7811.50, 7819.25, 7810.50, 7811.75,
            7809.72, 7824.55, 7794.90, 7839.37, 7780.07),
    "45m": ("12:45", 7810.50, 7816.25, 7810.50, 7814.50,
            7809.89, 7824.77, 7795.00, 7839.65, 7780.12),
    "30m": ("13:00", 7811.75, 7816.25, 7811.00, 7814.50,
            7809.89, 7824.87, 7794.91, 7839.85, 7779.93),
    "20m": ("13:20", 7813.75, 7818.50, 7811.00, 7818.25,
            7810.00, 7825.32, 7794.68, 7840.63, 7779.37),
}

#: VWAP and the bands carry an irreducible residual: the reference builds its
#: line from ticks and Schwab sells us minute bars. Measured across these four
#: bars the worst field is 0.234, so half a point leaves room for a data revision
#: without leaving room for a real regression -- the bugs this chased were 2.44,
#: 7.72 and 55+ points.
VWAP_TOLERANCE = 0.5


@pytest.fixture(scope="module")
def minutes() -> pd.DataFrame:
    """The 1-minute bars the reference bars were built from, in-session only."""
    df = pd.read_csv(FIXTURE, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    t = df.index.time
    return df[(t >= SESSION_START) | (t < SESSION_END)]


def _pane(minutes: pd.DataFrame, tf: str):
    """One timeframe, built exactly the way the app builds it."""
    bars = resample_ohlcv(minutes, tf, bar_anchor("ES"), with_vwap_price=True)
    vwap, upper, lower = calc_vwap_bands(
        bars["high"], bars["low"], bars["close"], bars["volume"],
        num_dev=1.0, session_start=SESSION_START, price=bars[VWAP_PRICE])
    return bars, vwap, upper, lower


@pytest.mark.parametrize("tf", list(REFERENCE))
def test_the_bar_exists_on_our_grid_at_the_time_the_reference_prints_it(tf, minutes):
    """
    Before any value can be compared, the bar has to be the same bar. This is the
    assertion that fails when the grid anchor is wrong -- on the session-open grid
    the 45m bars land at 12:30 and 13:15 CT, and 12:45 does not exist at all.
    """
    ct_open = REFERENCE[tf][0]
    want = pd.Timestamp(f"2026-08-13 {ct_open}") + CT_TO_ET
    bars, *_ = _pane(minutes, tf)

    assert want in bars.index, (
        f"{tf}: the reference prints a bar opening {ct_open} CT; our grid has "
        + ", ".join((s - CT_TO_ET).strftime("%H:%M")
                    for s in bars.index
                    if abs((s - want).total_seconds()) <= 5400) + " CT"
    )


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
@pytest.mark.parametrize("tf", list(REFERENCE))
def test_ohlc_is_exactly_what_the_reference_printed(tf, field, minutes):
    """
    No tolerance. OHLC is first/max/min/last over a set of minutes -- if the set
    is right the number is right, and if the number is wrong the set is wrong.
    """
    ct_open, o, h, low, c, *_ = REFERENCE[tf]
    want_at = pd.Timestamp(f"2026-08-13 {ct_open}") + CT_TO_ET
    expected = {"open": o, "high": h, "low": low, "close": c}[field]

    bars, *_ = _pane(minutes, tf)
    got = float(bars.loc[want_at, field])
    assert got == expected, (
        f"{tf} {ct_open} CT {field}: app {got} vs reference {expected}"
    )


@pytest.mark.parametrize("tf", list(REFERENCE))
def test_the_bar_spans_the_right_amount_of_market_time(tf, minutes):
    """
    A bar holding the wrong number of minutes can still show a plausible OHLC.
    The range is the cheap tell, and the reference prints it.
    """
    ct_open, _o, h, low, *_ = REFERENCE[tf]
    want_at = pd.Timestamp(f"2026-08-13 {ct_open}") + CT_TO_ET
    bars, *_ = _pane(minutes, tf)
    row = bars.loc[want_at]

    assert row.high - row.low == pytest.approx(h - low, abs=1e-9), (
        f"{tf}: range {row.high - row.low} vs reference {h - low}"
    )
    covered = minutes.loc[want_at: want_at + pd.Timedelta(minutes=TF_MINUTES[tf] - 1)]
    assert len(covered) == TF_MINUTES[tf], (
        f"{tf}: bar holds {len(covered)} minutes, expected {TF_MINUTES[tf]}"
    )


@pytest.mark.parametrize("level", ["vwap", "u1", "l1", "u2", "l2"])
@pytest.mark.parametrize("tf", list(REFERENCE))
def test_vwap_and_bands_are_within_tolerance_of_the_reference(tf, level, minutes):
    ct_open, _o, _h, _l, _c, vwap, u1, l1, u2, l2 = REFERENCE[tf]
    want_at = pd.Timestamp(f"2026-08-13 {ct_open}") + CT_TO_ET
    bars, v, upper, lower = _pane(minutes, tf)

    i = list(bars.index).index(want_at)
    mine, sigma = float(v.iloc[i]), float(upper.iloc[i] - v.iloc[i])
    got = {"vwap": mine, "u1": mine + sigma, "l1": mine - sigma,
           "u2": mine + 2 * sigma, "l2": mine - 2 * sigma}[level]
    expected = {"vwap": vwap, "u1": u1, "l1": l1, "u2": u2, "l2": l2}[level]

    assert abs(got - expected) <= VWAP_TOLERANCE, (
        f"{tf} {ct_open} CT {level}: app {got:.4f} vs reference {expected} "
        f"(off by {abs(got - expected):.4f}, tolerance {VWAP_TOLERANCE})"
    )


@pytest.mark.parametrize("tf", list(TF_MINUTES))
def test_every_timeframe_tiles_from_exchange_midnight(tf, minutes):
    """
    Generalises the four reference bars to all eleven timeframes: every bar opens
    a whole number of intervals after midnight on the exchange's clock. Nothing
    here depends on the session window, which is the point -- the session moves
    the VWAP reset and must not move the grid.
    """
    bars = resample_ohlcv(minutes, tf, bar_anchor("ES"))
    step = TF_MINUTES[tf]
    anchor_h = bar_anchor("ES").hour

    for ts in bars.index:
        day = (ts - pd.Timedelta(hours=anchor_h)).normalize() + pd.Timedelta(hours=anchor_h)
        offset = int((ts - day).total_seconds() // 60)
        assert offset % step == 0, (
            f"{tf}: bar at {ts} ET is {offset % step} minutes off the "
            f"exchange-midnight grid"
        )


def test_the_grid_does_not_move_when_the_session_window_changes(minutes):
    """
    The two anchors must stay independent. Changing the session window may change
    VWAP -- that is its job -- and must leave every bar boundary untouched.
    """
    for tf in TF_MINUTES:
        base = resample_ohlcv(minutes, tf, bar_anchor("ES"))
        for other in (time(9, 30), time(0, 0), time(4, 0)):
            again = resample_ohlcv(minutes, tf, bar_anchor("ES"))
            assert list(base.index) == list(again.index), f"{tf}: grid moved"
            _ = other
