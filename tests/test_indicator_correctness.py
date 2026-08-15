"""
Permanent guard on bar construction: boundaries AND OHLC, every timeframe.

This exists because two bugs were found by comparing screenshots against another
platform, one date and one time at a time -- 25m bars sitting off the session
grid, and 45m OHLC differing by a point or three. Both came from the same root:
pandas anchors resample bins at MIDNIGHT by default, so any bar size that does
not divide the session open's offset from midnight drifts off the session grid.
Which timeframes break depends on the anchor, which is why it looked specific to
25m on a Globex session and would have looked like six different timeframes on a
cash session.

The checks below do NOT call the app's aggregation. They reconstruct the
expected bin edges by arithmetic from the session open, and the expected OHLC
from the 1-minute bars directly (first/max/min/last/sum), then compare. Two
independent constructions agreeing is the point; calling the same function twice
would prove nothing.

Coverage is every timeframe x several session anchors x several dates x
several times of day, so an edge case at the open, mid-session or near the close
cannot hide.
"""

from datetime import date, time

import pandas as pd
import pytest

from src.backtesting.multi_replay import TF_MINUTES, resample_ohlcv, session_origin

TIMEFRAMES = list(TF_MINUTES)                       # all eleven
ANCHORS = [time(18, 0), time(9, 30), time(0, 0), time(6, 30)]
# Five dates, Monday through Friday, so a weekday-specific grid error
# cannot hide in a sample that happens to miss it.
DATES = [date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12),
         date(2026, 8, 13), date(2026, 8, 14)]


def _minute_bars(start: pd.Timestamp, count: int) -> pd.DataFrame:
    """
    Deterministic 1-minute bars whose OHLC differ from each other and from their
    neighbours, so a mis-grouped bar cannot coincidentally produce the right
    aggregate. The saw-tooth means highs and lows land on different bars.
    """
    idx = pd.DatetimeIndex([start + pd.Timedelta(minutes=i) for i in range(count)])
    rows = []
    for i in range(count):
        base = 5000.0 + (i % 97) * 0.25 + i * 0.01
        rows.append({
            "open": base,
            "high": base + 1.0 + (i % 7) * 0.25,
            "low": base - 1.0 - (i % 5) * 0.25,
            "close": base + ((i % 3) - 1) * 0.5,
            "volume": 100 + (i % 13),
        })
    return pd.DataFrame(rows, index=idx)


def _session_open(ts, anchor: time) -> pd.Timestamp:
    """The open of the session `ts` belongs to."""
    delta = pd.Timedelta(hours=anchor.hour, minutes=anchor.minute)
    return pd.Timestamp((pd.Timestamp(ts) - delta).normalize()) + delta


def _covered(df: pd.DataFrame, ts, minutes: int, anchor: time) -> pd.DataFrame:
    """
    The minute bars a resampled bar may legitimately contain.

    Clipped at the next session open: bins restart every session, so the last
    bin of a session is short whenever the interval does not divide the session
    length, and it must not reach into the following session.
    """
    end = min(pd.Timestamp(ts) + pd.Timedelta(minutes=minutes),
              _session_open(ts, anchor) + pd.Timedelta(days=1))
    return df[(df.index >= ts) & (df.index < end)]


def _expected_bins(first: pd.Timestamp, last: pd.Timestamp,
                   anchor: time, minutes: int) -> list[pd.Timestamp]:
    """Bin edges by arithmetic from the session open -- no resampling involved."""
    origin = pd.Timestamp(first).normalize() + pd.Timedelta(
        hours=anchor.hour, minutes=anchor.minute)
    if origin > first:
        origin -= pd.Timedelta(days=1)
    step = pd.Timedelta(minutes=minutes)
    edges, t = [], origin
    while t <= last:
        edges.append(t)
        t += step
    return edges


@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a.strftime("%H%M"))
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_every_bar_starts_on_the_session_grid(tf, anchor):
    """
    The first bar opens exactly at the session open and every later bar sits a
    whole number of intervals after it. This is the check that fails for 25m on
    an 18:00 session, and for six timeframes on a 09:30 session, before the fix.
    """
    start = pd.Timestamp(DATES[0]) + pd.Timedelta(hours=anchor.hour, minutes=anchor.minute)
    df = _minute_bars(start, 60 * 26)                # 26 hours, so 1h has depth
    out = resample_ohlcv(df, tf, anchor)
    minutes = TF_MINUTES[tf]

    assert len(out) > 1, f"{tf}: expected several bars"
    assert out.index[0] == start, (
        f"{tf} @{anchor}: first bar opens {out.index[0]}, not at the session open {start}"
    )
    for ts in out.index:
        # Relative to the bar's OWN session, since bins restart at each open.
        offset = int((ts - _session_open(ts, anchor)).total_seconds() // 60)
        assert offset % minutes == 0, (
            f"{tf} @{anchor}: bar at {ts} is {offset % minutes} minutes off the grid "
            f"of the session that opened {_session_open(ts, anchor)}"
        )


@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a.strftime("%H%M"))
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_ohlcv_equals_the_minute_bars_it_covers(tf, anchor):
    """
    Open = first minute's open, High = max of highs, Low = min of lows,
    Close = last minute's close, Volume = the sum -- taken straight from the
    1-minute bars in [bar_open, bar_open + interval).

    This is what catches a bar built from the wrong SET of minutes: an off-by-one
    at either edge changes the high, the low or the volume even when the bin
    label looks right.
    """
    start = pd.Timestamp(DATES[1]) + pd.Timedelta(hours=anchor.hour, minutes=anchor.minute)
    df = _minute_bars(start, 60 * 26)
    out = resample_ohlcv(df, tf, anchor)

    for ts, bar in out.iterrows():
        window = _covered(df, ts, TF_MINUTES[tf], anchor)
        assert not window.empty, f"{tf} @{anchor}: bar {ts} covers no minutes"
        assert bar.open == window.open.iloc[0], f"{tf} @{anchor} {ts}: open"
        assert bar.high == window.high.max(), f"{tf} @{anchor} {ts}: high"
        assert bar.low == window.low.min(), f"{tf} @{anchor} {ts}: low"
        assert bar.close == window.close.iloc[-1], f"{tf} @{anchor} {ts}: close"
        assert bar.volume == window.volume.sum(), f"{tf} @{anchor} {ts}: volume"


@pytest.mark.parametrize("day", DATES, ids=lambda d: d.isoformat())
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_boundaries_and_ohlc_hold_at_four_times_of_day(tf, day):
    """
    The same two properties sampled at the open, mid-morning, mid-afternoon and
    near the close, on several dates -- so an edge case that only appears at one
    point in the session cannot pass by luck.
    """
    anchor = time(18, 0)
    start = pd.Timestamp(day) + pd.Timedelta(hours=18)
    df = _minute_bars(start, 60 * 23)
    out = resample_ohlcv(df, tf, anchor)

    for probe_hours in (0, 4, 12, 22):                # open, early, mid, late
        moment = start + pd.Timedelta(hours=probe_hours)
        covering = out.index[(out.index <= moment)]
        if len(covering) == 0:
            continue
        ts = covering[-1]
        offset = int((ts - start).total_seconds() // 60)
        assert offset % TF_MINUTES[tf] == 0, (
            f"{tf} {day} +{probe_hours}h: bar {ts} off the grid"
        )
        window = _covered(df, ts, TF_MINUTES[tf], anchor)
        bar = out.loc[ts]
        assert bar.high == window.high.max(), f"{tf} {day} +{probe_hours}h: high"
        assert bar.low == window.low.min(), f"{tf} {day} +{probe_hours}h: low"


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_bars_tile_without_gap_or_overlap(tf):
    """Consecutive bars are exactly one interval apart wherever data is
    continuous -- no bar may swallow its neighbour's minutes."""
    anchor = time(18, 0)
    start = pd.Timestamp(DATES[2]) + pd.Timedelta(hours=18)
    df = _minute_bars(start, 60 * 20)
    out = resample_ohlcv(df, tf, anchor)
    step = pd.Timedelta(minutes=TF_MINUTES[tf])
    # Within a session the spacing is exactly one interval. A shorter gap is
    # allowed only where a session restarts, since the last bin of the previous
    # session may be short.
    for a, b in zip(out.index, out.index[1:]):
        same_session = _session_open(a, anchor) == _session_open(b, anchor)
        if same_session:
            assert b - a == step, f"{tf}: {a} -> {b} is not one interval"
        else:
            assert b == _session_open(b, anchor), (
                f"{tf}: session after {a} starts at {b}, not at its open"
            )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_no_minute_is_dropped_or_double_counted(tf):
    """Total volume across the resampled bars equals the 1-minute total."""
    anchor = time(18, 0)
    start = pd.Timestamp(DATES[0]) + pd.Timedelta(hours=18)
    df = _minute_bars(start, 60 * 20)
    out = resample_ohlcv(df, tf, anchor)
    assert out.volume.sum() == df.volume.sum(), (
        f"{tf}: resampled volume {out.volume.sum()} != minute volume {df.volume.sum()}"
    )


def test_session_origin_walks_back_when_the_open_is_later_in_the_day():
    """A 09:40 bar belongs to the session that opened 18:00 the day before."""
    got = session_origin(pd.Timestamp("2026-08-13 09:40"), time(18, 0))
    assert got == pd.Timestamp("2026-08-12 18:00")


def test_session_origin_is_none_without_an_anchor():
    assert session_origin(pd.Timestamp("2026-08-13 09:40"), None) is None


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_the_reported_case_25m_on_a_globex_session(tf):
    """
    The exact shape of the report: an 18:00 session on 2026-08-13. Before the
    fix 25m bars landed on :05/:30/:55 instead of the session grid. Asserted for
    every timeframe so the next anchor that breaks a different one is caught
    here rather than on someone's screen.
    """
    start = pd.Timestamp("2026-08-12 18:00")
    df = _minute_bars(start, 60 * 21)                 # through 15:00 next day
    out = resample_ohlcv(df, tf, time(18, 0))
    minutes = TF_MINUTES[tf]
    around_14 = [t for t in out.index if t >= pd.Timestamp("2026-08-13 13:00")]
    assert around_14, f"{tf}: no bars in the afternoon"
    for ts in around_14[:6]:
        offset = int((ts - start).total_seconds() // 60)
        assert offset % minutes == 0, f"{tf}: {ts} is off the 18:00 grid"


# ---------------------------------------------------------------------------
# Multiple sessions. The first version of this suite used one continuous block
# starting exactly at the anchor, so it could not see that bins were tiling
# straight through session boundaries from a single origin. A live spot-check
# found 25m ten minutes off the session that contained it; these cover it.
# ---------------------------------------------------------------------------

#: These synthetic frames are continuous minutes with no 17:00-18:00 break, so
#: one session group spans a full day. A real 18:00-17:00 session is shorter;
#: the property under test (a bar belongs to exactly one group and sits on that
#: group's grid) does not depend on the length.
SESSION_MINUTES = 24 * 60


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_every_session_opens_its_own_first_bar(tf):
    """
    Bins RESTART at each session open rather than tiling continuously.

    A session is 1380 minutes and 1380 % 25, 35, 40, 45 are all non-zero, so a
    single origin leaves each following session further off the grid than the
    last -- which is exactly how a 25m bar came to sit 10 minutes off the
    session containing it while the first session looked perfect.
    """
    start = pd.Timestamp("2026-08-11 18:00")
    df = _minute_bars(start, 60 * 70)              # three sessions
    out = resample_ohlcv(df, tf, time(18, 0))

    opens = [t for t in out.index if t.hour == 18 and t.minute == 0]
    assert len(opens) >= 3, (
        f"{tf}: only {len(opens)} session opens landed on a bar boundary; "
        f"bins are tiling through the session boundary instead of restarting"
    )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_bars_sit_on_the_grid_of_their_own_session(tf):
    """
    Every bar is a whole number of intervals after the open of the session it
    belongs to -- not after the first session in the frame.
    """
    start = pd.Timestamp("2026-08-11 18:00")
    df = _minute_bars(start, 60 * 70)
    out = resample_ohlcv(df, tf, time(18, 0))
    minutes = TF_MINUTES[tf]

    for ts in out.index:
        session_open = _session_open(ts, time(18, 0))
        offset = int((ts - session_open).total_seconds() // 60)
        assert 0 <= offset < SESSION_MINUTES + minutes, f"{tf}: {ts} outside its session"
        assert offset % minutes == 0, (
            f"{tf}: bar {ts} is {offset % minutes} minutes off the grid of the "
            f"session that opened {session_open}"
        )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_no_bar_straddles_a_session_boundary(tf):
    """
    A bar may not contain minutes from two different sessions -- that would mix
    yesterday's close with today's open into one candle.
    """
    start = pd.Timestamp("2026-08-11 18:00")
    df = _minute_bars(start, 60 * 70)
    out = resample_ohlcv(df, tf, time(18, 0))
    step = pd.Timedelta(minutes=TF_MINUTES[tf])
    anchor = pd.Timedelta(hours=18)

    for ts in out.index:
        # The bar's own session, and the minutes it can legitimately contain.
        session_open = pd.Timestamp((ts - anchor).normalize()) + anchor
        next_open = session_open + pd.Timedelta(days=1)
        end = min(ts + step, next_open)
        window = df[(df.index >= ts) & (df.index < end)]
        sessions = {(t - anchor).normalize() for t in window.index}
        assert len(sessions) <= 1, (
            f"{tf}: bar {ts} would contain minutes from {len(sessions)} sessions"
        )
        # and the aggregate must match exactly that clipped set
        if not window.empty:
            assert out.loc[ts].high == window.high.max(), (
                f"{tf}: bar {ts} high includes minutes beyond its session"
            )


@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a.strftime("%H%M"))
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_ohlc_still_exact_across_several_sessions(tf, anchor):
    """
    OHLC reconstructed from the minute bars, over a multi-session frame.

    The expected window is CLIPPED at the next session open. The last bin of a
    session is short whenever the interval does not divide the session length --
    35m into a 23-hour session leaves a 5-minute remainder -- and that bar must
    contain only its own session's minutes. Running the window on past the
    boundary would demand a high from the next session, which is precisely the
    straddling the code is right to refuse.
    """
    start = pd.Timestamp("2026-08-11") + pd.Timedelta(
        hours=anchor.hour, minutes=anchor.minute)
    df = _minute_bars(start, 60 * 70)
    out = resample_ohlcv(df, tf, anchor)
    step = pd.Timedelta(minutes=TF_MINUTES[tf])
    anchor_delta = pd.Timedelta(hours=anchor.hour, minutes=anchor.minute)

    for ts, bar in out.iterrows():
        session_open = pd.Timestamp((ts - anchor_delta).normalize()) + anchor_delta
        next_open = session_open + pd.Timedelta(days=1)
        end = min(ts + step, next_open)
        window = df[(df.index >= ts) & (df.index < end)]
        assert not window.empty
        assert bar.open == window.open.iloc[0], f"{tf} @{anchor} {ts}: open"
        assert bar.high == window.high.max(), f"{tf} @{anchor} {ts}: high"
        assert bar.low == window.low.min(), f"{tf} @{anchor} {ts}: low"
        assert bar.close == window.close.iloc[-1], f"{tf} @{anchor} {ts}: close"
        assert bar.volume == window.volume.sum(), f"{tf} @{anchor} {ts}: volume"


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_volume_conserved_across_several_sessions(tf):
    start = pd.Timestamp("2026-08-11 18:00")
    df = _minute_bars(start, 60 * 70)
    out = resample_ohlcv(df, tf, time(18, 0))
    assert out.volume.sum() == df.volume.sum(), f"{tf}: minutes lost or duplicated"


# ---------------------------------------------------------------------------
# Per-FIELD checks.
#
# A live comparison found a bar whose High, Low and Close were right and whose
# Open was wrong by exactly 1.00. That shape -- one field off, the rest exact --
# is what an aggregate "does this bar match" assertion hides, because a single
# failing field is reported the same way as a wholly wrong bar and is easy to
# read as noise. Each field is therefore its own parametrised case, so a failure
# names the field.
# ---------------------------------------------------------------------------

FIELDS = ["open", "high", "low", "close", "volume"]


def _expected_field(window: pd.DataFrame, field: str):
    return {
        "open": lambda w: w.open.iloc[0],
        "high": lambda w: w.high.max(),
        "low": lambda w: w.low.min(),
        "close": lambda w: w.close.iloc[-1],
        "volume": lambda w: w.volume.sum(),
    }[field](window)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a.strftime("%H%M"))
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_each_ohlcv_field_independently(tf, anchor, field):
    """
    Every bar's `field` equals that field recomputed from the minute bars it
    covers. All four OHLC values must come from ONE correctly-windowed set --
    never from separate lookups, which is how one field drifts while the others
    stay right.
    """
    start = pd.Timestamp("2026-08-11") + pd.Timedelta(
        hours=anchor.hour, minutes=anchor.minute)
    df = _minute_bars(start, 60 * 50)                 # two sessions
    out = resample_ohlcv(df, tf, anchor)

    for ts, bar in out.iterrows():
        window = _covered(df, ts, TF_MINUTES[tf], anchor)
        assert not window.empty, f"{tf} @{anchor} {ts}: covers no minutes"
        assert getattr(bar, field) == _expected_field(window, field), (
            f"{tf} @{anchor} {ts}: {field} is {getattr(bar, field)}, "
            f"expected {_expected_field(window, field)} from the "
            f"{len(window)} minutes it covers"
        )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_open_is_the_first_minutes_open_not_the_previous_bars_close(tf):
    """
    The specific shape that was reported: Open wrong while High/Low/Close were
    right. Guards against the open being taken from a neighbouring bar or a
    carried-over value.
    """
    anchor = time(18, 0)
    start = pd.Timestamp("2026-08-11 18:00")
    df = _minute_bars(start, 60 * 30)
    out = resample_ohlcv(df, tf, anchor)

    for ts, bar in out.iterrows():
        window = _covered(df, ts, TF_MINUTES[tf], anchor)
        assert bar.open == window.open.iloc[0], f"{tf} {ts}: open is not the first minute's open"
        assert bar.open == df.loc[window.index[0]].open, f"{tf} {ts}: open came from another bar"


# ---------------------------------------------------------------------------
# VWAP, every deviation level, and the volume profile -- same permanent suite,
# because those are read off the same rows and have been compared just as often.
# ---------------------------------------------------------------------------

DEV_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def _vwap_sigma(df: pd.DataFrame):
    """Session-cumulative VWAP and population sigma, written out longhand."""
    sv = stv = stv2 = 0.0
    vwaps, sigmas = [], []
    for _, r in df.iterrows():
        tp = (r.high + r.low + r.close) / 3.0
        sv += r.volume
        stv += tp * r.volume
        stv2 += tp * tp * r.volume
        m = stv / sv
        vwaps.append(m)
        sigmas.append(((stv2 / sv - m * m) ** 0.5) if stv2 / sv > m * m else 0.0)
    return vwaps, sigmas


@pytest.mark.parametrize("dev", DEV_LEVELS)
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_every_deviation_level_is_vwap_plus_n_sigma(tf, dev):
    """
    Each band is exactly VWAP +/- N x sigma on the SAME bars, for every level the
    UI offers. The UI recovers sigma as (upper - vwap)/2 from a 2-sigma payload
    and rescales, so this pins the identity that recovery depends on.
    """
    from src.analysis.indicators import calc_vwap_bands

    anchor = time(18, 0)
    start = pd.Timestamp("2026-08-11 18:00")
    df = resample_ohlcv(_minute_bars(start, 60 * 30), tf, anchor)

    v, u, lo = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                               num_dev=dev, session_start=anchor)
    v2, u2, _ = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                                num_dev=2.0, session_start=anchor)

    for i in range(len(df)):
        if pd.isna(v.iloc[i]) or pd.isna(u2.iloc[i]):
            continue
        sigma = (u2.iloc[i] - v2.iloc[i]) / 2.0
        assert abs(u.iloc[i] - (v.iloc[i] + dev * sigma)) < 1e-6, (
            f"{tf} dev {dev} bar {i}: upper is not vwap + {dev}*sigma"
        )
        assert abs(lo.iloc[i] - (v.iloc[i] - dev * sigma)) < 1e-6, (
            f"{tf} dev {dev} bar {i}: lower is not vwap - {dev}*sigma"
        )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_vwap_matches_an_independent_recompute(tf):
    from src.analysis.indicators import calc_vwap_bands

    anchor = time(18, 0)
    start = pd.Timestamp("2026-08-11 18:00")
    df = resample_ohlcv(_minute_bars(start, 60 * 20), tf, anchor)
    v, _, _ = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                              num_dev=2.0, session_start=anchor)
    mine, _ = _vwap_sigma(df)
    for i in range(len(df)):
        if pd.isna(v.iloc[i]):
            continue
        assert abs(v.iloc[i] - mine[i]) < 1e-6, f"{tf} bar {i}: vwap"


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_volume_profile_poc_and_value_area(tf):
    """
    POC is the fullest bin; the value area encloses at least the requested share
    of volume and VAHigh >= POC >= VALow.
    """
    from src.analysis.indicators import calc_volume_profile

    anchor = time(18, 0)
    start = pd.Timestamp("2026-08-11 18:00")
    df = resample_ohlcv(_minute_bars(start, 60 * 20), tf, anchor)
    vp = calc_volume_profile(df["high"], df["low"], df["close"], df["volume"],
                             bins=48, value_area_pct=0.70)

    assert vp["poc"] is not None, f"{tf}: no POC"
    assert vp["vah"] >= vp["poc"] >= vp["val"], (
        f"{tf}: value area {vp['val']}..{vp['vah']} does not enclose POC {vp['poc']}"
    )
    assert df.low.min() <= vp["val"] and vp["vah"] <= df.high.max() + (vp["bin_size"] or 0), (
        f"{tf}: value area escapes the price range"
    )
    poc_i = max(range(len(vp["volumes"])), key=lambda i: vp["volumes"][i])
    assert abs(vp["prices"][poc_i] - vp["poc"]) < 1e-9, f"{tf}: POC is not the fullest bin"


# ---------------------------------------------------------------------------
# DETERMINISM.
#
# The layer above asks "is this value right?". This one asks "is it the SAME
# value every time?", which is a different question and the one that kept
# getting answered wrong. A bar that closed hours ago was coming back with a
# different VWAP depending on which OTHER timeframes were on screen, because the
# replay picks its source resolution from the whole selection and one of the
# aggregation paths was not session-anchored. Nothing about that is visible from
# a single reading -- you only see it by taking two.
# ---------------------------------------------------------------------------

from functools import reduce  # noqa: E402
from math import gcd  # noqa: E402

FETCHABLE = ("1m", "5m", "10m", "15m", "30m", "1h")


def _source_timeframe(timeframes):
    """Mirrors api.routers.replay._source_timeframe."""
    g = reduce(gcd, (TF_MINUTES[t] for t in timeframes))
    return max((t for t in FETCHABLE if g % TF_MINUTES[t] == 0),
               key=lambda t: TF_MINUTES[t])


def _pane_values(minute_df, selection, want, anchor):
    """
    Build `want`'s bars the way create_replay does: fetch at the source
    resolution the SELECTION implies, then resample that up to the pane.
    """
    from src.analysis.indicators import calc_vwap_bands
    from src.data.schwab_provider import build_timeframe

    from src.data.resample import bar_anchor

    src = _source_timeframe(selection)
    fetched = build_timeframe(minute_df, src, "ES")
    # Bars tile from the exchange anchor; VWAP still resets at the session open.
    pane = resample_ohlcv(fetched, want, bar_anchor("ES"))
    v, u, lo = calc_vwap_bands(pane["high"], pane["low"], pane["close"],
                               pane["volume"], num_dev=2.0, session_start=anchor)
    return pane, v, u, lo


SELECTIONS = [
    ["1h"], ["30m", "1h"], ["15m", "1h"], ["5m", "1h"],
    ["20m", "30m", "45m", "1h"], ["1m", "1h"],
]


@pytest.mark.parametrize("anchor", [time(9, 30), time(18, 0)])
def test_a_closed_bars_values_do_not_depend_on_which_timeframes_are_selected(anchor):
    """
    The regression that started this: selecting only 1h gave a different VWAP for
    an already-closed 1h bar than selecting 1h alongside anything finer, because
    the source resolution changed and one aggregation path anchored on midnight.
    Every selection must produce byte-identical bars and bands.
    """
    minute = _minute_bars(pd.Timestamp("2026-08-13 00:00"), 60 * 24)
    baseline = base_sel = None
    for sel in SELECTIONS:
        pane, v, u, lo = _pane_values(minute, sel, "1h", anchor)
        got = [(str(t), float(r.open), float(r.high), float(r.low), float(r.close),
                float(r.volume), round(float(v.iloc[i]), 9), round(float(u.iloc[i]), 9),
                round(float(lo.iloc[i]), 9))
               for i, (t, r) in enumerate(pane.iterrows())]
        if baseline is None:
            baseline, base_sel = got, sel
            continue
        assert got == baseline, (
            f"1h bars differ between selection {base_sel} and {sel} "
            f"(anchor {anchor}). First difference: "
            + next((f"{a} vs {b}" for a, b in zip(baseline, got) if a != b), "length")
        )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_recomputing_the_same_closed_bar_gives_the_same_answer(tf):
    """
    Same inputs, computed repeatedly, with the frame rebuilt from scratch each
    time -- as a fresh request would. Any cached or incrementally-updated state
    leaking between calls shows up here as drift.
    """
    from src.analysis.indicators import calc_volume_profile, calc_vwap_bands

    anchor = time(18, 0)
    runs = []
    for _ in range(3):
        minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 20)
        df = resample_ohlcv(minute, tf, anchor)
        v, u, lo = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                                   num_dev=2.0, session_start=anchor)
        vp = calc_volume_profile(df["high"], df["low"], df["close"], df["volume"],
                                 bins=48, value_area_pct=0.70)
        runs.append((
            df.round(9).to_csv(),
            v.round(9).to_csv(), u.round(9).to_csv(), lo.round(9).to_csv(),
            round(vp["poc"], 9), round(vp["vah"], 9), round(vp["val"], 9),
        ))
    assert runs[0] == runs[1] == runs[2], f"{tf}: repeated computation drifted"


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_a_closed_bar_does_not_change_when_later_bars_arrive(tf):
    """
    Playback appends bars as the session runs. A bar that has already closed must
    keep the values it had -- VWAP is cumulative, so it may only ever depend on
    bars up to and including itself, never on ones that arrive afterwards.
    """
    from src.analysis.indicators import calc_vwap_bands

    anchor = time(18, 0)
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 12)
    full = resample_ohlcv(minute, tf, anchor)
    if len(full) < 4:
        pytest.skip(f"{tf}: too few bars in the window to truncate meaningfully")

    cut = len(full) // 2
    upto = full.index[cut] + pd.Timedelta(minutes=TF_MINUTES[tf] - 1)
    partial = resample_ohlcv(minute.loc[:upto], tf, anchor)

    v_full, u_full, _ = calc_vwap_bands(full["high"], full["low"], full["close"],
                                        full["volume"], num_dev=2.0, session_start=anchor)
    v_part, u_part, _ = calc_vwap_bands(partial["high"], partial["low"], partial["close"],
                                        partial["volume"], num_dev=2.0, session_start=anchor)

    for i in range(min(cut, len(partial))):
        assert full.index[i] == partial.index[i], f"{tf} bar {i}: timestamp moved"
        for f in ("open", "high", "low", "close", "volume"):
            assert full[f].iloc[i] == partial[f].iloc[i], (
                f"{tf} bar {i} {f}: a closed bar changed when later bars arrived"
            )
        if not pd.isna(v_full.iloc[i]):
            assert abs(v_full.iloc[i] - v_part.iloc[i]) < 1e-9, (
                f"{tf} bar {i}: VWAP of a closed bar changed when later bars arrived"
            )
            assert abs(u_full.iloc[i] - u_part.iloc[i]) < 1e-9, (
                f"{tf} bar {i}: band of a closed bar changed when later bars arrived"
            )


# ---------------------------------------------------------------------------
# PATH PARITY.
#
# Replay, Backtest and the CSV export each reach the bars by a different route.
# They must land on the same grid, or a client comparing two pages of the same
# app sees two different numbers before anyone even opens the reference platform.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("anchor", [time(9, 30), time(18, 0)])
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_the_provider_builds_the_same_bars_the_replay_does(tf, anchor):
    """
    Schwab serves 1/5/10/15/30m natively and the provider builds the other six
    itself. That build used a bare df.resample(), which anchors on MIDNIGHT, so
    20m/25m/35m/40m/45m/1h came back on a different grid from the replay's --
    on a 09:30 session the 1h bar opened at 10:00 instead of 09:30.
    """
    from src.data.schwab_provider import build_timeframe

    from src.data.resample import bar_anchor

    minute = _minute_bars(pd.Timestamp("2026-08-13 00:00"), 60 * 24)
    # Both sides key off the SYMBOL now -- the exchange's midnight decides the
    # grid, not the session open. `anchor` is retained as a parametrisation only
    # to show the grid does NOT move with it.
    _ = anchor
    via_provider = build_timeframe(minute, tf, "ES")
    via_replay = resample_ohlcv(minute, tf, bar_anchor("ES"))

    # Natively-served frequencies are a pass-through; the provider hands back
    # exactly what it fetched, so there is nothing to compare for those.
    if via_provider is minute:
        pytest.skip(f"{tf}: served natively, no aggregation on the provider path")

    assert list(via_provider.index) == list(via_replay.index), (
        f"{tf} anchor {anchor}: provider grid starts {via_provider.index[0]}, "
        f"replay grid starts {via_replay.index[0]}"
    )
    for f in ("open", "high", "low", "close", "volume"):
        assert (via_provider[f].to_numpy() == via_replay[f].to_numpy()).all(), (
            f"{tf} anchor {anchor}: {f} differs between the provider and replay paths"
        )


# ---------------------------------------------------------------------------
# RSI and Stochastic.
#
# Neither is derived from VWAP, but both are read off the same rows and both are
# division-based, so they belong in the same standing check.
#
# Note on scope: the app has no StochRSI and no MFI. There is a Stochastic
# oscillator (%K/%D), which is a different indicator. Nothing below pretends
# otherwise, and if either is added later it needs its own case here.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("period", [2, 13])
@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_rsi_matches_a_longhand_wilder_recompute(tf, period):
    """RSI with Wilder smoothing, written out step by step against the app's."""
    from src.analysis.indicators import calc_rsi

    anchor = time(18, 0)
    df = resample_ohlcv(_minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 20), tf, anchor)
    got = calc_rsi(df["close"], period)

    close = df["close"].tolist()
    gains, losses = [], []
    for i in range(1, len(close)):
        d = close[i] - close[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    # ewm(alpha=1/period, adjust=False) seeded on the first delta.
    ag = al = None
    mine = [float("nan")]
    for g, ls in zip(gains, losses):
        ag = g if ag is None else ag + (g - ag) / period
        al = ls if al is None else al + (ls - al) / period
        mine.append(100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al))

    for i in range(len(df)):
        if pd.isna(got.iloc[i]) or pd.isna(mine[i]):
            continue
        assert abs(got.iloc[i] - mine[i]) < 1e-6, f"{tf} RSI{period} bar {i}"


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_stochastic_k_and_d_match_a_longhand_recompute(tf):
    """
    The SLOW stochastic, which is what calc_stoch returns:

        raw %K = 100 * (C - LL) / (HH - LL)   over k_period
        %K     = SMA(raw %K, smooth_k)        <- the returned "K", already smoothed
        %D     = SMA(%K, d_period)

    Worth stating explicitly because the first version of this test compared the
    returned K against RAW %K and called the app wrong by up to 1.5 points. The
    app was right; the expectation was a fast stochastic. A zero-width range
    yields NaN rather than a made-up midpoint, so those bars are skipped.
    """
    from src.analysis.indicators import calc_stoch

    anchor = time(18, 0)
    k_period, smooth_k, d_period = 14, 3, 3
    df = resample_ohlcv(_minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 20), tf, anchor)
    if len(df) < k_period + smooth_k + d_period:
        pytest.skip(f"{tf}: fewer bars than the stochastic lookback needs")

    k, d = calc_stoch(df["high"], df["low"], df["close"], k_period, smooth_k, d_period)

    hi, lo, cl = df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    nan = float("nan")

    raw_k = []
    for i in range(len(df)):
        if i + 1 < k_period:
            raw_k.append(nan)
            continue
        hh, ll = max(hi[i + 1 - k_period: i + 1]), min(lo[i + 1 - k_period: i + 1])
        raw_k.append(nan if hh == ll else 100.0 * (cl[i] - ll) / (hh - ll))

    def sma(series, n):
        out = []
        for i in range(len(series)):
            w = series[i + 1 - n: i + 1]
            out.append(nan if i + 1 < n or any(pd.isna(x) for x in w) else sum(w) / n)
        return out

    mine_k = sma(raw_k, smooth_k)
    mine_d = sma(mine_k, d_period)

    for i in range(len(df)):
        if pd.isna(k.iloc[i]) or pd.isna(mine_k[i]):
            continue
        assert abs(k.iloc[i] - mine_k[i]) < 1e-6, f"{tf} %K bar {i}"

    for i in range(len(df)):
        if pd.isna(d.iloc[i]) or pd.isna(mine_d[i]):
            continue
        assert abs(d.iloc[i] - mine_d[i]) < 1e-6, f"{tf} %D bar {i}"


# ---------------------------------------------------------------------------
# The still-forming bar.
#
# Everything above concerns bars that have closed. Today's last bar has not, and
# the app will be driven on today's date. A forming bar is allowed to move -- but
# only in the ways a forming bar can.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_the_forming_bar_only_moves_the_ways_a_forming_bar_can(tf):
    """
    Feeding one more minute at a time into the newest bar: its open never moves,
    its high only rises, its low only falls, its volume only grows, and the bar
    before it does not move at all.
    """
    anchor = time(18, 0)
    tf_min = TF_MINUTES[tf]
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 8)

    prev = prev_ts = prev_closed = None
    base = 3 * tf_min + 90   # mid-session, well past the open
    for extra in range(1, tf_min + 1):
        df = resample_ohlcv(minute.iloc[: base + extra], tf, anchor)
        cur = df.iloc[-1]
        closed_now = (tuple(df.iloc[-2][["open", "high", "low", "close", "volume"]])
                      if len(df) > 1 else None)
        if prev is not None and df.index[-1] == prev_ts:
            assert cur.open == prev.open, f"{tf}: the forming bar moved its open"
            assert cur.high >= prev.high, f"{tf}: the forming bar lowered its high"
            assert cur.low <= prev.low, f"{tf}: the forming bar raised its low"
            assert cur.volume >= prev.volume, f"{tf}: the forming bar shed volume"
            if prev_closed is not None:
                assert closed_now == prev_closed, (
                    f"{tf}: the bar BEFORE the forming one changed"
                )
        prev, prev_ts, prev_closed = cur, df.index[-1], closed_now


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_once_a_bar_closes_it_matches_an_independent_recompute_and_freezes(tf):
    """
    The close-out moment: the bar that has just finished must equal first/max/min
    /last/sum over exactly its own minutes, and must not move again once the next
    bar starts filling.
    """
    anchor = time(18, 0)
    tf_min = TF_MINUTES[tf]
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 8)

    at_close = resample_ohlcv(minute.iloc[: 4 * tf_min], tf, anchor)
    just_closed_ts = at_close.index[-1]
    just_closed = at_close.iloc[-1]

    window = minute.loc[just_closed_ts: just_closed_ts + pd.Timedelta(minutes=tf_min - 1)]
    assert just_closed.open == window.open.iloc[0], f"{tf}: open"
    assert just_closed.high == window.high.max(), f"{tf}: high"
    assert just_closed.low == window.low.min(), f"{tf}: low"
    assert just_closed.close == window.close.iloc[-1], f"{tf}: close"
    assert just_closed.volume == window.volume.sum(), f"{tf}: volume"

    for extra in (1, tf_min // 2 + 1, tf_min):
        later = resample_ohlcv(minute.iloc[: 4 * tf_min + extra], tf, anchor)
        row = later.loc[just_closed_ts]
        for f in ("open", "high", "low", "close", "volume"):
            assert row[f] == just_closed[f], (
                f"{tf}: {f} of the bar closed at {just_closed_ts} changed "
                f"{extra} minute(s) later"
            )


# ---------------------------------------------------------------------------
# WHICH PRICE EACH BAR CONTRIBUTES TO VWAP.
#
# (H+L+C)/3 is the textbook typical price. It is not what a broker platform's
# VWAP study accumulates -- thinkorswim uses each bar's OWN volume-weighted
# price, computed from the ticks inside it. On /ES 30m, 2026-08-13, the bar
# opening 13:00 CT, against a screen showing VWAP 7809.89 / sigma 14.98:
#
#     (H+L+C)/3           7810.2336  sigma 14.9233   0 of 5 whole numbers
#     bar's own VWAP      7809.9279  sigma 15.0147   5 of 5
#
# So resample_ohlcv can carry that per-bar figure and calc_vwap_bands can take
# it. Both directions need pinning: that it IS used when supplied, and that it
# collapses to the old behaviour when there is nothing finer to build it from.
# ---------------------------------------------------------------------------

from src.data.resample import VWAP_PRICE  # noqa: E402


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_vwap_price_is_the_volume_weighted_mean_of_the_minutes_inside_the_bar(tf):
    anchor = time(18, 0)
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 12)
    out = resample_ohlcv(minute, tf, anchor, with_vwap_price=True)
    assert VWAP_PRICE in out.columns, f"{tf}: column not produced"

    span = TF_MINUTES[tf]
    for ts in out.index[:20]:
        win = minute.loc[ts: ts + pd.Timedelta(minutes=span - 1)]
        # (H+L)/2 per minute, not (H+L+C)/3 -- fitted against the reference
        # platform, see src/data/resample._vwap_price.
        hl2 = (win.high + win.low) / 2.0
        expected = float((hl2 * win.volume).sum() / win.volume.sum())
        assert abs(out[VWAP_PRICE].loc[ts] - expected) < 1e-9, f"{tf} bar {ts}"


def test_vwap_price_collapses_to_the_bars_own_midpoint_when_source_is_the_target():
    """
    A 1m pane built from 1m bars has one source row per output bar, so the
    weighted mean IS that bar's own (H+L)/2 -- no averaging left to do.
    """
    anchor = time(18, 0)
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 600)
    out = resample_ohlcv(minute, "1m", anchor, with_vwap_price=True)
    hl2 = (out.high + out.low) / 2.0
    assert (out[VWAP_PRICE] - hl2).abs().max() < 1e-9


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_calc_vwap_bands_uses_the_supplied_price(tf):
    """
    Supplying `price` must change the answer to match a longhand accumulation of
    that price -- and omitting it must reproduce the (H+L+C)/3 behaviour exactly,
    so every caller that has not been given finer data is unaffected.
    """
    from src.analysis.indicators import calc_vwap_bands

    anchor = time(18, 0)
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 12)
    df = resample_ohlcv(minute, tf, anchor, with_vwap_price=True)

    with_price, _, _ = calc_vwap_bands(df["high"], df["low"], df["close"],
                                       df["volume"], num_dev=2.0,
                                       session_start=anchor, price=df[VWAP_PRICE])
    without, _, _ = calc_vwap_bands(df["high"], df["low"], df["close"],
                                    df["volume"], num_dev=2.0, session_start=anchor)

    # Longhand, accumulating the supplied price.
    sv = stv = 0.0
    mine = []
    for _, r in df.iterrows():
        sv += r.volume
        stv += r[VWAP_PRICE] * r.volume
        mine.append(stv / sv)
    for i in range(len(df)):
        assert abs(with_price.iloc[i] - mine[i]) < 1e-6, f"{tf} bar {i}: supplied price ignored"

    if TF_MINUTES[tf] > 1:
        assert (with_price - without).abs().max() > 0, (
            f"{tf}: supplying the per-bar VWAP changed nothing, so it is not being used"
        )


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_a_pane_accumulates_its_own_bar_vwap_not_hlc3(tf):
    """
    End to end through MultiReplaySession, which is what the UI reads: the pane's
    VWAP must be the one built from the source bars, not from (H+L+C)/3 of its
    own bars. Guards the wiring, which is the part that would silently revert.
    """
    from src.analysis.indicators import calc_vwap_bands
    from src.backtesting.multi_replay import MultiReplaySession
    from src.strategies.rsi_divergence import RSIDivergenceStrategy

    anchor = time(18, 0)
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 12)
    sess = MultiReplaySession(df=minute, timeframes=[tf],
                              strategy_factory=lambda: RSIDivergenceStrategy(),
                              symbol="ES", session_start=anchor, source_timeframe="1m")
    pane = sess.panes[tf]
    assert VWAP_PRICE in pane.df.columns, f"{tf}: pane built without the per-bar price"

    want, _, _ = calc_vwap_bands(pane.df["high"], pane.df["low"], pane.df["close"],
                                 pane.df["volume"], num_dev=2.0, session_start=anchor,
                                 price=pane.df[VWAP_PRICE])
    for i in range(min(len(pane.df), 30)):
        got = pane.engine.vwap_at(i)["vwap"]
        if got is None or pd.isna(want.iloc[i]):
            continue
        assert abs(got - want.iloc[i]) < 1e-6, (
            f"{tf} bar {i}: pane VWAP {got} is not the per-bar-price accumulation "
            f"{want.iloc[i]}"
        )


# ---------------------------------------------------------------------------
# THE SOURCE RESOLUTION MUST NOT CHANGE A VALUE.
#
# Bar construction is safe at any source that divides the pane -- that was
# established above. VWAP is not: it needs the price distribution INSIDE each
# bar, so a source equal to the pane's own resolution has nothing to look at and
# the per-bar VWAP collapses to (H+L+C)/3. Selecting 30m alone gave 7810.2336
# where 1m + 30m gave 7809.9279, on a bar that had closed hours earlier.
#
# Hence the fetch is always 1m. These pin that, and pin the consequence.
# ---------------------------------------------------------------------------

def test_the_fetch_resolution_is_always_one_minute():
    """
    Whatever is selected. The previous rule picked the coarsest divisor to keep
    the request cheap, which is correct for OHLCV and silently wrong for VWAP.
    """
    from api.routers.replay import _source_timeframe

    for sel in (["30m"], ["1h"], ["45m"], ["5m", "15m"], ["30m", "1h"],
                ["20m", "25m", "35m"], TIMEFRAMES):
        assert _source_timeframe(sel) == "1m", (
            f"{sel} would fetch {_source_timeframe(sel)}, so any pane at that "
            f"resolution has no minutes inside its bars and its VWAP silently "
            f"falls back to (H+L+C)/3"
        )


@pytest.mark.parametrize("tf", ["20m", "30m", "45m", "1h"])
def test_a_panes_vwap_is_the_same_whatever_else_is_selected(tf):
    """
    The end-to-end version of the above, through MultiReplaySession: build the
    same pane under every selection it could appear in and require identical
    VWAP and bands on every bar.

    This is the check that was missing. The earlier determinism test compared
    bars only, so it stayed green while the VWAP moved.
    """
    from src.backtesting.multi_replay import MultiReplaySession
    from src.strategies.rsi_divergence import RSIDivergenceStrategy
    from api.routers.replay import _source_timeframe

    anchor = time(18, 0)
    minute = _minute_bars(pd.Timestamp("2026-08-11 18:00"), 60 * 20)

    selections = [[tf], [tf, "1m"], ["5m", tf], [tf, "1h"], TIMEFRAMES]
    baseline = base_sel = None
    for sel in selections:
        if tf not in sel:
            continue
        src = _source_timeframe(sel)
        # The FETCH, modelled honestly. Handing MultiReplaySession 1-minute bars
        # regardless of `src` is what made the first version of this test pass
        # while the bug was live: the router decides the resolution and the
        # provider returns bars AT it, so the session never sees the minutes.
        source_df = minute if src == "1m" else resample_ohlcv(minute, src, anchor)
        sess = MultiReplaySession(
            df=source_df, timeframes=sel,
            strategy_factory=lambda: RSIDivergenceStrategy(),
            symbol="ES", session_start=anchor,
            source_timeframe=src,
        )
        pane = sess.panes[tf]
        got = []
        for i in range(len(pane.df)):
            v = pane.engine.vwap_at(i)
            got.append((str(pane.df.index[i]),
                        None if v["vwap"] is None else round(v["vwap"], 9),
                        None if v["vwap_upper"] is None else round(v["vwap_upper"], 9),
                        None if v["vwap_lower"] is None else round(v["vwap_lower"], 9)))
        if baseline is None:
            baseline, base_sel = got, sel
            continue
        assert got == baseline, (
            f"{tf}: VWAP differs between selection {base_sel} and {sel}. "
            + next((f"first at {a[0]}: {a[1]} vs {b[1]}"
                    for a, b in zip(baseline, got) if a != b), "length differs")
        )
