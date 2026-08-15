"""
indicators.py
=============

RSI and Stochastic calculations, extracted verbatim from
ui/components/charts.py so the FastAPI backend and the Streamlit app share one
implementation instead of forking it. No logic changes from the originals.
"""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd


def calc_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def calc_stoch(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, smooth_k: int = 3, d_period: int = 3):
    lowest = low.rolling(k_period).min()
    highest = high.rolling(k_period).max()
    rng = (highest - lowest).replace(0, np.nan)
    raw_k = 100.0 * (close - lowest) / rng
    k = raw_k.rolling(smooth_k).mean()   # Slow %K
    d = k.rolling(d_period).mean()        # Slow %D
    return k, d


def calc_vwap_bands(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series | None,
    num_dev: float = 2.0,
    session_start: time | None = None,
    price: pd.Series | None = None,
):
    """Session VWAP with volume-weighted standard-deviation bands.

    The standard broker-platform formulation (num dev up +2, num dev dn -2,
    timeframe DAY):

        typical price  tp = (high + low + close) / 3
        vwap              = Σ(tp · vol) / Σ(vol)
        variance          = Σ(vol · (tp − vwap)²) / Σ(vol)
        bands             = vwap ± num_dev · √variance

    Both sums are CUMULATIVE WITHIN A TRADING SESSION and reset at each new
    session -- that reset is what makes it VWAP rather than a rolling
    average, and it is why the line jumps at a session boundary instead of
    carrying yesterday's mean forward. At the first bar of a session the
    variance is still zero, so vwap == upper == lower there by construction;
    the bands fan out as volume accumulates. That convergence is expected.

    `session_start` is the session's opening wall-clock time and decides WHERE
    that reset lands. Pass it whenever the session can cross midnight: an
    18:00-17:00 Globex session is one continuous session, but anchoring on the
    calendar date splits it at 00:00 and collapses the bands mid-session.
    None (or 00:00) keeps the plain calendar-date behaviour, which is correct
    for a 24-hour chart and for any session contained within one date.

    The variance is volume-weighted around the running VWAP, not a plain
    rolling std of price, so the bands widen with genuinely heavy two-sided
    trade rather than with volatility alone.

    Returns (vwap, upper, lower). All three are all-NaN when `volume` is
    absent or sums to zero for a session -- VWAP is undefined without volume,
    and inventing it (e.g. treating every bar as volume 1, which silently
    degrades to a mean of typical price) would produce a plausible-looking
    line that is not VWAP. Callers should treat NaN as "not available" and
    simply not draw it.
    """
    empty = pd.Series(np.nan, index=close.index)
    if volume is None:
        return empty, empty.copy(), empty.copy()

    vol = pd.to_numeric(volume, errors="coerce").astype("float64").fillna(0.0)

    # WHICH PRICE EACH BAR CONTRIBUTES
    #
    # (H+L+C)/3 is the textbook typical price and the default here. It is NOT
    # what a broker platform's VWAP study uses: thinkorswim accumulates each
    # bar's OWN volume-weighted price -- its vwap() fundamental, computed from
    # the ticks inside that bar -- which is a different number whenever trade
    # is not evenly spread across the bar's range.
    #
    # The gap is small per bar and compounds over a session. Measured on /ES
    # 30m, 2026-08-13, bar opening 13:00 CT, Globex anchor, against a screen
    # showing VWAP 7809.89 / sigma 14.98:
    #
    #     (H+L+C)/3            7810.2336  sigma 14.9233   0 of 5 whole numbers
    #     bar's own VWAP       7809.9279  sigma 15.0147   5 of 5, -1 sigma exact
    #
    # `price` carries that per-bar figure when the caller has finer data to
    # build it from -- see resample_ohlcv(with_vwap_price=True), which computes
    # it from the source bars each output bar was aggregated from. Left None it
    # falls back to (H+L+C)/3, which is also exactly what the finer calculation
    # collapses to when the source and the target are the same resolution.
    if price is not None:
        tp = pd.to_numeric(price, errors="coerce").astype("float64")
        fallback = (high.astype("float64") + low.astype("float64")
                    + close.astype("float64")) / 3.0
        tp = tp.where(tp.notna(), fallback)
    else:
        tp = (high.astype("float64") + low.astype("float64")
              + close.astype("float64")) / 3.0

    # Group by SESSION so each session accumulates on its own. A DatetimeIndex
    # is required for that; without one there are no sessions to reset on, so
    # fall back to a single continuous accumulation.
    #
    # Anchoring on the calendar date is only correct when the session does not
    # cross midnight. For an overnight/Globex session (18:00-17:00) the reset
    # landed at 00:00 -- six hours INTO the session -- so the bands collapsed
    # to zero width in the middle of a continuous session and rebuilt from
    # scratch. Measured on ES 2026-08-10..11: band width 24.555 at 23:55, then
    # 0.000 at 00:00. Shifting the index back by session_start puts the
    # session's own open at midnight of the shifted clock, so normalize()
    # groups the whole session together.
    #
    # For a session that does not wrap (09:30-16:00) this is identical to the
    # calendar date, because every bar already falls on one date.
    if isinstance(close.index, pd.DatetimeIndex):
        anchor = pd.Timedelta(0)
        if session_start is not None:
            anchor = pd.Timedelta(
                hours=session_start.hour,
                minutes=session_start.minute,
                seconds=session_start.second,
            )
        day = (close.index - anchor).normalize()
    else:
        day = pd.Index([0] * len(close))

    cum_vol = vol.groupby(day).cumsum()
    cum_pv = (tp * vol).groupby(day).cumsum()

    safe_vol = cum_vol.where(cum_vol > 0)
    vwap = cum_pv / safe_vol

    # Σ(vol·(tp − vwap)²) expanded to Σ(vol·tp²)/Σvol − vwap², which needs one
    # cumulative pass instead of a second one per bar against a moving mean.
    cum_pv2 = (tp.pow(2) * vol).groupby(day).cumsum()
    variance = (cum_pv2 / safe_vol) - vwap.pow(2)
    std = np.sqrt(variance.clip(lower=0.0))   # clip: float error can dip below 0

    return vwap, vwap + num_dev * std, vwap - num_dev * std


def compute_rangebreaks(index: pd.DatetimeIndex, gap_factor: float = 8.0,
                        max_breaks: int = 400) -> list[dict]:
    """Periods a time axis should skip so bars read as one continuous series.

    Session filtering keeps only in-session bars, but a date axis still
    reserves space for the hours it removed -- an 09:30-16:00 session leaves
    an ~18h void every night and ~60h every weekend, and the chart renders as
    islands of candles separated by blank stretches.

    Breaks are derived from the timestamps themselves rather than from
    hardcoded market hours, so whatever produced the gap -- session filter,
    weekend, holiday, venue maintenance, or a hole in the data -- is skipped
    without anything needing to know which instrument trades when.

    A gap qualifies only if it is well clear of the normal bar spacing.
    gap_factor 8 -- 40 minutes on a 5-minute chart -- was chosen by measuring
    both a dense and a sparse series rather than picked for feel:

        ES  5m, one week   2 breaks at every factor from 1.5 to 20
        BTC 5m, two weeks  144 / 40 / 18 / 11 breaks at 1.5 / 4 / 8 / 20

    Dense in-session data is insensitive to the threshold -- only the
    overnight voids ever qualify. A sparse series is very sensitive, and a low
    factor there starts compressing ordinary holes in the data, which
    misrepresents elapsed time. 8 keeps session and weekend boundaries (those
    run to hundreds of times the median) while leaving a handful of missing
    bars visible as the gap they are.

    Returns Plotly rangebreak dicts: [{"bounds": [start, end]}, ...].
    """
    if len(index) < 3:
        return []
    deltas = np.diff(index.values).astype("timedelta64[ns]").astype("int64")
    deltas = deltas[deltas > 0]
    if deltas.size == 0:
        return []
    step = int(np.median(deltas))
    if step <= 0:
        return []

    out: list[dict] = []
    prev = index[0]
    for cur in index[1:]:
        if len(out) >= max_breaks:
            break
        if (cur - prev).value > step * gap_factor:
            # Start one step after the last bar so it keeps its full width,
            # and end exactly on the next one.
            out.append({"bounds": [
                str(prev + pd.Timedelta(step, unit="ns")),
                str(cur),
            ]})
        prev = cur
    return out


def calc_volume_profile(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series | None,
    bins: int = 48,
    value_area_pct: float = 0.70,
) -> dict:
    """Volume Profile with POC and the value-area bounds.

    Standard construction:

    * the price range is split into `bins` equal buckets;
    * each bar spreads its volume evenly across the buckets its high-low range
      touches, rather than dumping it all at the close -- a wide bar genuinely
      traded across its whole range, and close-only assignment produces a
      spiky profile that moves with the timeframe;
    * **POC** (point of control) is the bucket holding the most volume;
    * the **value area** grows outward from the POC, repeatedly taking
      whichever neighbour -- above or below -- holds more volume, until
      `value_area_pct` of total volume is enclosed. **VAH** and **VAL** are its
      upper and lower price bounds.

    Returns {"prices", "volumes", "poc", "vah", "val", "bin_size"}; every
    value is None/empty when there is no volume to profile, since a profile
    without volume is not a thing that can be approximated.
    """
    empty = {"prices": [], "volumes": [], "poc": None, "val": None,
             "vah": None, "bin_size": None}
    if volume is None or len(close) == 0:
        return empty

    vol = pd.to_numeric(volume, errors="coerce").astype("float64").fillna(0.0)
    if float(vol.sum()) <= 0:
        return empty

    lo = float(low.min())
    hi = float(high.max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return empty

    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    bucket_vol = np.zeros(bins, dtype="float64")

    h = high.astype("float64").to_numpy()
    l = low.astype("float64").to_numpy()
    v = vol.to_numpy()
    width = (hi - lo) / bins

    for bar_low, bar_high, bar_vol in zip(l, h, v):
        if bar_vol <= 0:
            continue
        first = int(np.clip((bar_low - lo) // width, 0, bins - 1))
        last = int(np.clip((bar_high - lo) // width, 0, bins - 1))
        touched = last - first + 1
        bucket_vol[first:last + 1] += bar_vol / touched

    total = bucket_vol.sum()
    if total <= 0:
        return empty

    poc_i = int(bucket_vol.argmax())
    # Grow outward from the POC, always taking the richer side.
    target = total * value_area_pct
    covered = bucket_vol[poc_i]
    below, above = poc_i, poc_i
    while covered < target and (below > 0 or above < bins - 1):
        take_below = bucket_vol[below - 1] if below > 0 else -1.0
        take_above = bucket_vol[above + 1] if above < bins - 1 else -1.0
        if take_above >= take_below:
            above += 1
            covered += take_above
        else:
            below -= 1
            covered += take_below

    return {
        "prices": [float(x) for x in centers],
        "volumes": [float(x) for x in bucket_vol],
        "poc": float(centers[poc_i]),
        "val": float(edges[below]),
        "vah": float(edges[above + 1]),
        "bin_size": float(width),
    }
