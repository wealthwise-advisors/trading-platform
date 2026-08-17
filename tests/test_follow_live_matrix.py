"""
Following the live market across EVERY timeframe, offset and date.

Written because the first version of this feature was verified on a 1m base and
shipped a bug that only appears on coarser ones. A 1m base makes the source and
the clock the same resolution, which hides an entire class of failure. So this
does not test "a timeframe" -- it tests all eleven the UI offers, at several
positions within each bar, across dates chosen to break assumptions.

THE INVARIANT
-------------
Every bar that has been EMITTED must be a bar that has actually closed:

    bar_start + timeframe <= now

That single property is what both bugs violated. A bar emitted before it closed
has a high, low, close and volume that are still moving, so the next refetch
disagrees with it -- which the revised-history guard then reports, jamming the
follow permanently. Asserting the invariant directly catches the cause rather
than the symptom, on every pane and after every poll.

WHY OFFSETS MATTER
------------------
The bug depended on where "now" falls inside the current bar. Polled one minute
into a 5m bar, the trim must cut back a whole bar; polled at the boundary it must
not. Both ends of that, and the middle, are tested for every timeframe.

WHY THE ANCHOR MATTERS
----------------------
Bars tile from bar_anchor(symbol), which is 01:00 for futures -- not midnight and
not the session open. So 25m, 35m, 40m and 45m bins land at irregular offsets
relative to 09:30 and cannot be reasoned about by dividing the clock time. The
trim asks resample_ohlcv where the bins actually are for exactly that reason, and
these cases are here to keep it honest.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.backtesting.multi_replay import (
    MultiReplaySession, TF_MINUTES, trim_to_closed_bars,
)
from src.strategies.ma_crossover import MACrossoverStrategy

#: Every timeframe the Live Replay page offers, in UI order.
ALL_TIMEFRAMES = ["1m", "5m", "10m", "15m", "20m", "25m",
                  "30m", "35m", "40m", "45m", "1h"]

#: Dates picked to break assumptions rather than to be representative.
DATES = [
    datetime(2026, 1, 5, 9, 30),     # ordinary Monday
    datetime(2026, 3, 9, 9, 30),     # day after US DST begins
    datetime(2026, 11, 2, 9, 30),    # day after US DST ends
    datetime(2026, 12, 31, 9, 30),   # year end
    datetime(2028, 2, 29, 9, 30),    # leap day
]


def _bars(open_at: datetime, first: int, count: int) -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [open_at + timedelta(minutes=i) for i in range(first, first + count)])
    close = [4500 + (i % 37) * 0.25 + i * 0.01 for i in range(first, first + count)]
    return pd.DataFrame(
        {"open": close, "high": [c + 1.0 for c in close],
         "low": [c - 1.0 for c in close], "close": close,
         "volume": [100 + (i % 11) for i in range(first, first + count)]},
        index=idx,
    )


def _build(df, timeframes):
    return MultiReplaySession(
        df=df, timeframes=timeframes,
        strategy_factory=lambda: MACrossoverStrategy(fast=9, slow=21),
        symbol="ES", source_timeframe="1m",
    )


def _drain(session):
    while not session.is_done:
        session.tick()


def assert_only_closed_bars_emitted(session, now, where=""):
    """
    THE invariant. Checked on every pane, not only the base.

    A pane's emitted bars are df[:cursor]; each must have closed by `now`.
    """
    now = pd.Timestamp(now)
    for tf, pane in session.panes.items():
        delta = pd.Timedelta(minutes=TF_MINUTES[tf])
        emitted = pane.df.iloc[:pane.cursor]
        if emitted.empty:
            continue
        last = emitted.index[-1]
        assert last + delta <= now, (
            f"{where}: {tf} pane emitted the bar opening {last}, which closes at "
            f"{last + delta}, but it is only {now}. That bar is still forming."
        )


def _follow(base_or_set, open_at, minutes, offset_s, polls, step=1):
    """
    Create at `minutes` past the open plus `offset_s`, drain, then poll `polls`
    times at `step`-minute intervals. Returns total source bars taken.
    """
    tfs = [base_or_set] if isinstance(base_or_set, str) else list(base_or_set)
    base = min(tfs, key=lambda t: TF_MINUTES[t])

    now = open_at + timedelta(minutes=minutes, seconds=offset_s)
    df = trim_to_closed_bars(_bars(open_at, 0, minutes), "1m", base, "ES", now)
    if df.empty:
        pytest.skip(f"no closed {base} bar yet at {minutes}m")

    session = _build(df, tfs)
    _drain(session)
    assert_only_closed_bars_emitted(session, now, f"{tfs} at creation")

    taken = 0
    for i in range(polls):
        minutes += step
        now = open_at + timedelta(minutes=minutes, seconds=offset_s)
        result = session.extend(_bars(open_at, 0, minutes), now=now)

        assert "revised" not in (result["reason"] or ""), (
            f"{tfs} JAMMED on poll {i + 1} at {now}: {result['reason']}")
        taken += result["added"]
        _drain(session)
        assert_only_closed_bars_emitted(session, now, f"{tfs} after poll {i + 1}")

    return taken


class TestEveryTimeframeFollowsTheMarket:
    """One base at a time, polled every minute across at least one bar boundary."""

    @pytest.mark.parametrize("base", ALL_TIMEFRAMES)
    def test_it_never_jams_and_keeps_advancing(self, base):
        minutes = TF_MINUTES[base] * 4 + 7      # several whole bars, plus a part
        polls = TF_MINUTES[base] + 3            # far enough to cross a boundary
        taken = _follow(base, DATES[0], minutes, 30, polls)
        assert taken >= polls - TF_MINUTES[base], (
            f"{base}: only {taken} source bars taken over {polls} polls")

    @pytest.mark.parametrize("base", ALL_TIMEFRAMES)
    def test_the_tape_actually_moves_forward(self, base):
        bm = TF_MINUTES[base]
        now = DATES[0] + timedelta(minutes=bm * 4, seconds=30)
        df = trim_to_closed_bars(_bars(DATES[0], 0, bm * 4), "1m", base, "ES", now)
        session = _build(df, [base])
        _drain(session)
        started = session.market_time

        # Two more whole bars' worth of minutes.
        later = DATES[0] + timedelta(minutes=bm * 6, seconds=30)
        session.extend(_bars(DATES[0], 0, bm * 6), now=later)
        _drain(session)

        assert session.market_time >= started + timedelta(minutes=bm), (
            f"{base}: tape did not advance ({started} -> {session.market_time})")
        assert_only_closed_bars_emitted(session, later, base)


class TestEveryPositionInsideABar:
    """
    The offset is what the original bug turned on: one minute into a 5m bar the
    trim must drop a whole bar, at the boundary it must not.
    """

    @pytest.mark.parametrize("base", ALL_TIMEFRAMES)
    def test_creation_never_keeps_an_unfinished_bar(self, base):
        bm = TF_MINUTES[base]
        total = bm * 3
        # Every minute across a whole bar, at three points inside each minute.
        for extra in range(bm + 1):
            for sec in (0, 1, 59):
                minutes = total + extra
                now = DATES[0] + timedelta(minutes=minutes, seconds=sec)
                df = trim_to_closed_bars(
                    _bars(DATES[0], 0, minutes), "1m", base, "ES", now)
                if df.empty:
                    continue
                session = _build(df, [base])
                _drain(session)
                assert_only_closed_bars_emitted(
                    session, now, f"{base} at +{extra}m{sec}s")

    @pytest.mark.parametrize("base", ["5m", "15m", "25m", "45m", "1h"])
    def test_following_works_from_any_offset(self, base):
        bm = TF_MINUTES[base]
        for offset_s in (0, 1, 30, 59):
            _follow(base, DATES[0], bm * 3 + 2, offset_s, polls=bm + 2)


class TestTimeframeCombinations:
    """
    What the UI actually produces: several panes at once. The base is the finest
    selected, so the same pane set behaves differently depending on what else is
    ticked -- adding 1m to a 5m selection changes the clock.
    """

    COMBOS = [
        ["1m", "5m"],
        ["5m", "15m"],
        ["5m", "30m", "1h"],
        ["10m", "20m", "40m"],
        ["25m", "35m", "45m"],          # none divides another
        ["1m", "5m", "15m", "30m", "1h"],
        ALL_TIMEFRAMES,                  # everything ticked
    ]

    @pytest.mark.parametrize("combo", COMBOS, ids=lambda c: "+".join(c))
    def test_the_whole_grid_follows_without_jamming(self, combo):
        base = min(combo, key=lambda t: TF_MINUTES[t])
        coarsest = max(combo, key=lambda t: TF_MINUTES[t])
        # Enough history for the coarsest pane to have several bars.
        minutes = TF_MINUTES[coarsest] * 3 + 11
        _follow(combo, DATES[0], minutes, 30,
                polls=min(TF_MINUTES[base] + 3, 25))

    @pytest.mark.parametrize("combo", COMBOS, ids=lambda c: "+".join(c))
    def test_no_pane_shows_a_bar_that_has_not_closed(self, combo):
        coarsest = max(combo, key=lambda t: TF_MINUTES[t])
        base = min(combo, key=lambda t: TF_MINUTES[t])
        minutes = TF_MINUTES[coarsest] * 2 + 13
        now = DATES[0] + timedelta(minutes=minutes, seconds=20)
        df = trim_to_closed_bars(_bars(DATES[0], 0, minutes), "1m", base, "ES", now)
        session = _build(df, combo)
        _drain(session)
        assert_only_closed_bars_emitted(session, now, "+".join(combo))


class TestAcrossDates:
    """
    Dates chosen to break things: both DST switches, a year end and a leap day.

    Timestamps are naive Eastern throughout, so a DST change must not shift a bin
    -- but the anchor arithmetic is where that assumption would show up, so it is
    checked rather than asserted in prose.
    """

    @pytest.mark.parametrize("open_at", DATES, ids=lambda d: d.date().isoformat())
    @pytest.mark.parametrize("base", ["1m", "5m", "30m", "45m", "1h"])
    def test_following_works_on_any_date(self, base, open_at):
        _follow(base, open_at, TF_MINUTES[base] * 3 + 4, 30,
                polls=min(TF_MINUTES[base] + 2, 20))

    @pytest.mark.parametrize("open_at", DATES, ids=lambda d: d.date().isoformat())
    def test_the_trim_lands_on_the_same_relative_bar_every_date(self, open_at):
        # 46 minutes of data, polled 30s into minute 46, on a 5m base: the answer
        # should be "cut back to the last whole 5 minutes" regardless of the date.
        now = open_at + timedelta(minutes=46, seconds=30)
        kept = trim_to_closed_bars(_bars(open_at, 0, 46), "1m", "5m", "ES", now)
        # Whatever the date, the kept tail must open a bin that has closed.
        five = pd.Timedelta(minutes=5)
        session = _build(kept, ["5m"])
        _drain(session)
        pane = session.panes["5m"]
        assert pane.df.index[pane.cursor - 1] + five <= pd.Timestamp(now)


class TestSessionShapes:
    """
    Overnight and 24-hour sessions, because the reported case was Globex
    (18:00-17:00) rather than RTH -- a session that spans midnight and pulls the
    previous calendar day in.
    """

    def test_an_overnight_span_follows(self):
        # 18:00 Sunday through midday Monday, as Globex produces.
        open_at = datetime(2026, 1, 4, 18, 0)
        _follow("5m", open_at, 60 * 18 + 16, 30, polls=8)

    def test_a_span_crossing_midnight_keeps_the_invariant(self):
        open_at = datetime(2026, 1, 4, 23, 30)
        now = open_at + timedelta(minutes=97, seconds=30)
        df = trim_to_closed_bars(_bars(open_at, 0, 97), "1m", "15m", "ES", now)
        session = _build(df, ["15m", "1h"])
        _drain(session)
        assert_only_closed_bars_emitted(session, now, "across midnight")

    def test_a_full_trading_day_then_follow(self):
        # 09:30-16:00 is 390 minutes; poll past the end of it.
        _follow("30m", datetime(2026, 1, 5, 9, 30), 390, 30, polls=12)


class TestNothingIsSilentlyDropped:
    """
    The trim must remove a bounded amount -- never a large slice.

    A trim that quietly discarded, say, an hour would look like a working feature
    while showing an hour-old tape, which is the failure mode this whole feature
    exists to remove.
    """

    @pytest.mark.parametrize("base", ALL_TIMEFRAMES)
    def test_it_never_drops_more_than_one_bar_worth(self, base):
        bm = TF_MINUTES[base]
        for extra in range(bm + 1):
            minutes = bm * 4 + extra
            now = DATES[0] + timedelta(minutes=minutes, seconds=30)
            kept = trim_to_closed_bars(
                _bars(DATES[0], 0, minutes), "1m", base, "ES", now)
            dropped = minutes - len(kept)
            # At most the forming source bar plus the unfinished base bin.
            assert dropped <= bm, (
                f"{base} at +{extra}m dropped {dropped} bars, more than one "
                f"{base} bar ({bm} minutes)")

    @pytest.mark.parametrize("base", ALL_TIMEFRAMES)
    def test_a_fully_historical_frame_is_untouched(self, base):
        # Every bar closed hours ago: nothing may be trimmed at all, or loading a
        # past date would silently lose its tail.
        minutes = TF_MINUTES[base] * 5
        long_after = DATES[0] + timedelta(days=1)
        kept = trim_to_closed_bars(
            _bars(DATES[0], 0, minutes), "1m", base, "ES", long_after)
        assert len(kept) == minutes
