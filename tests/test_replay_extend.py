"""
Tests for growing a live replay past the end of the snapshot it loaded.

A session replays a fixed frame of history. Running out of that frame is not
the same as running out of market -- while the replay was playing, the market
kept printing. `extend()` takes the newly-printed bars and lets the same
session carry on, keeping its clock, its tape and its strategy state.

The properties worth defending, in order of how badly they fail silently:

  1. Bars already replayed must not change. The client is showing them.
  2. A partially-formed bar must never be presented as closed.
  3. Coarse panes must recompute the bin that straddles the seam, not leave a
     truncated bar behind.
  4. Strategy state must survive the rebuild, since the engines are recreated.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.backtesting.multi_replay import MultiReplaySession, resample_ohlcv
from src.strategies.ma_crossover import MACrossoverStrategy


OPEN = datetime(2026, 1, 5, 9, 30)


def _bars(first: int, count: int) -> pd.DataFrame:
    """
    Bars [first, first + count) of ONE deterministic master series.

    Sliced from a single series rather than generated per call, because the
    sharpest test here compares a session that grew against a session handed
    everything at once. If the "new" bars were generated from their own index
    origin the two datasets would differ by construction, and the comparison
    would be measuring the fixture instead of the code. (They did, and it was.)
    """
    idx = pd.DatetimeIndex([OPEN + timedelta(minutes=i) for i in range(first, first + count)])
    close = [4500 + (i % 37) * 0.25 + i * 0.01 for i in range(first, first + count)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 1.0 for c in close],
            "low": [c - 1.0 for c in close],
            "close": close,
            "volume": [100 + (i % 11) for i in range(first, first + count)],
        },
        index=idx,
    )


def _off_grid(at: datetime) -> pd.DataFrame:
    """A single bar on a non-minute boundary, as a revision would arrive."""
    return pd.DataFrame(
        {"open": [4600.0], "high": [4601.0], "low": [4599.0],
         "close": [4600.5], "volume": [999]},
        index=pd.DatetimeIndex([at]),
    )


def _session(timeframes, bars=120):
    return MultiReplaySession(
        df=_bars(0, bars),
        timeframes=timeframes,
        strategy_factory=lambda: MACrossoverStrategy(fast=9, slow=21),
        symbol="ES",
        source_timeframe="1m",
    )


def _drain(session):
    """Play to the end of the loaded data."""
    while not session.is_done:
        session.tick()


def _minutes_held(session) -> int:
    """How far into the master series the session's data reaches."""
    return int((session.last_source_time - OPEN).total_seconds() // 60) + 1


def _next_bars(session, count):
    """The bars that print immediately after the session's data, same series."""
    return _bars(_minutes_held(session), count)


def _engine_state(session):
    """Everything the rebuild could plausibly disturb."""
    return {
        tf: (list(p.engine._equity), len(p.engine._completed_trades), p.cursor)
        for tf, p in session.panes.items()
    }


class TestGrowingASession:
    def test_a_finished_session_can_run_again(self):
        session = _session(["1m"])
        _drain(session)
        assert session.is_done
        before = session.total_ticks

        result = session.extend(_next_bars(session, 5))

        assert result["added"] == 5
        assert result["reason"] is None
        assert session.total_ticks == before + 5
        # The whole point: it is no longer finished.
        assert not session.is_done

    def test_the_clock_does_not_move_when_data_arrives(self):
        session = _session(["1m"])
        for _ in range(40):
            session.tick()
        at = session.market_time
        index = session._clock_index

        session.extend(_next_bars(session, 10))

        assert session.market_time == at
        assert session._clock_index == index

    def test_the_new_bars_are_then_playable(self):
        session = _session(["1m"])
        _drain(session)
        end_of_snapshot = session.market_time

        session.extend(_next_bars(session, 3))
        played = 0
        while not session.is_done:
            session.tick()
            played += 1

        assert played == 3
        assert session.market_time > end_of_snapshot

    def test_extending_repeatedly_keeps_working(self):
        session = _session(["1m"])
        _drain(session)
        for _ in range(4):
            assert session.extend(_next_bars(session, 2))["added"] == 2
            _drain(session)
        assert session.total_ticks == 120 + 8


class TestBarsAlreadyReplayed:
    def test_replayed_bars_are_identical_afterwards(self):
        session = _session(["1m", "15m"])
        for _ in range(60):
            session.tick()
        before = {
            tf: pane.df.iloc[:pane.cursor].copy()
            for tf, pane in session.panes.items()
        }

        session.extend(_next_bars(session, 30))

        for tf, pane in session.panes.items():
            after = pane.df.iloc[:len(before[tf])]
            pd.testing.assert_frame_equal(before[tf], after)

    def test_each_pane_keeps_its_cursor(self):
        session = _session(["1m", "5m", "15m"])
        for _ in range(75):
            session.tick()
        cursors = {tf: p.cursor for tf, p in session.panes.items()}

        session.extend(_next_bars(session, 20))

        assert {tf: p.cursor for tf, p in session.panes.items()} == cursors

    def test_revised_history_is_refused_outright(self):
        session = _session(["1m"])
        for _ in range(50):
            session.tick()
        before_total = session.total_ticks
        before_source = session._source_df.copy()

        # A revision landing INSIDE the already-replayed stretch. It adds no
        # timestamp to the resampled series: 09:40:30 falls into the existing
        # 09:40 bin and rewrites its high, low, close and volume. So a guard that
        # compares only timestamps sees nothing wrong -- which is exactly the
        # case that has to be caught, and the first version of this code did not.
        result = session.extend(_off_grid(datetime(2026, 1, 5, 9, 40, 30)))

        assert result["added"] == 0
        assert "revised" in result["reason"]
        assert session.total_ticks == before_total
        pd.testing.assert_frame_equal(before_source, session._source_df)

    def test_a_correction_beyond_the_replayed_point_is_accepted(self):
        # Same shape as above but stamped AFTER the clock. 50 ticks from 09:30
        # means bars through 10:19 have been issued, so a 10:45 revision touches
        # nothing on screen and taking it is safe.
        session = _session(["1m"])
        for _ in range(50):
            session.tick()

        result = session.extend(_off_grid(datetime(2026, 1, 5, 10, 45, 30)))

        assert result["added"] == 1
        assert result["reason"] is None


class TestStillFormingBars:
    def test_the_forming_bar_is_withheld(self):
        session = _session(["1m"])
        _drain(session)
        incoming = _next_bars(session, 3)

        # Polled halfway through the third bar: only the first two have closed.
        now = incoming.index[-1] + timedelta(seconds=30)
        result = session.extend(incoming, now=now)

        assert result["added"] == 2
        assert session.last_source_time == incoming.index[-2]

    def test_a_bar_is_complete_exactly_one_interval_after_its_stamp(self):
        session = _session(["1m"])
        _drain(session)
        incoming = _next_bars(session, 1)

        # One second early: not yet.
        assert session.extend(
            incoming, now=incoming.index[-1] + timedelta(seconds=59),
        )["added"] == 0
        # Exactly on the close: taken.
        assert session.extend(
            incoming, now=incoming.index[-1] + timedelta(minutes=1),
        )["added"] == 1

    def test_the_forming_bar_arrives_on_a_later_poll(self):
        session = _session(["1m"])
        _drain(session)
        incoming = _next_bars(session, 2)

        session.extend(incoming, now=incoming.index[-1])
        assert session.last_source_time == incoming.index[0]
        # Same frame, polled a minute later. The withheld bar is now closed.
        session.extend(incoming, now=incoming.index[-1] + timedelta(minutes=1))
        assert session.last_source_time == incoming.index[1]

    def test_all_forming_is_reported_rather_than_silently_empty(self):
        session = _session(["1m"])
        _drain(session)
        incoming = _next_bars(session, 1)
        result = session.extend(incoming, now=incoming.index[0])
        assert result["added"] == 0
        assert "still forming" in result["reason"]


class TestTheSeamOnCoarsePanes:
    # 100 one-minute bars from 09:30 run to 11:09, so the hourly bins are
    # 09:00 (30 minutes of it), 10:00 (full), and 11:00 holding just ten
    # minutes. 11:00 is the partial one -- the seam.
    SEAM = pd.Timestamp("2026-01-05 11:00")

    def test_a_partial_bin_is_recomputed_not_left_truncated(self):
        session = _session(["1m", "1h"], bars=100)
        _drain(session)
        partial = session.panes["1h"].df.loc[self.SEAM]
        assert partial["volume"] > 0

        # Fill more of that hour.
        session.extend(_next_bars(session, 30))
        healed = session.panes["1h"].df.loc[self.SEAM]

        assert healed["volume"] > partial["volume"]
        assert healed["high"] >= partial["high"]
        assert healed["low"] <= partial["low"]

    def test_the_healed_bin_matches_a_one_shot_resample(self):
        session = _session(["1m", "1h"], bars=100)
        _drain(session)
        session.extend(_next_bars(session, 30))

        # Bar for bar what the pane would be had all 130 bars been loaded at
        # once. This is the statement that the seam leaves no trace.
        oneshot = resample_ohlcv(_bars(0, 130), "1h", with_vwap_price=True)
        pd.testing.assert_frame_equal(
            session.panes["1h"].df, oneshot, check_freq=False,
        )

    def test_the_truncated_coarse_bar_was_never_emitted_in_the_first_place(self):
        # Why recomputing the seam is safe at all: a coarse bar is only emitted
        # once the CLOCK passes its close, and the clock cannot outrun the data.
        # So the partial 11:00 bar existed in the frame but was never sent, and
        # rewriting it changes nothing the client has seen.
        session = _session(["1m", "1h"], bars=100)
        _drain(session)
        pane = session.panes["1h"]
        assert self.SEAM in pane.df.index
        assert self.SEAM not in pane.df.iloc[:pane.cursor].index


class TestStateSurvivesTheRebuild:
    def test_the_equity_curve_and_trades_are_unchanged(self):
        # The engines are DESTROYED and rebuilt, so this is the assertion that
        # the replay-forward genuinely reproduces state rather than approximating
        # it. Compares the whole equity curve, not just its last value.
        session = _session(["1m", "5m"], bars=120)
        for _ in range(90):
            session.tick()
        before = _engine_state(session)

        session.extend(_next_bars(session, 15))

        assert _engine_state(session) == before

    def test_extending_then_playing_matches_loading_it_all_at_once(self):
        """
        The strongest statement available: a session that grew is bar-for-bar the
        same as one that had the data from the start. If the rebuild drifted, this
        is where it shows.
        """
        grown = _session(["1m", "5m"], bars=100)
        _drain(grown)
        grown.extend(_next_bars(grown, 40))
        _drain(grown)

        whole = MultiReplaySession(
            df=_bars(0, 140),
            timeframes=["1m", "5m"],
            strategy_factory=lambda: MACrossoverStrategy(fast=9, slow=21),
            symbol="ES",
            source_timeframe="1m",
        )
        _drain(whole)

        assert grown.total_ticks == whole.total_ticks
        assert grown.market_time == whole.market_time
        assert grown.bar_counts() == whole.bar_counts()
        for tf in ["1m", "5m"]:
            g, w = grown.panes[tf], whole.panes[tf]
            assert g.cursor == w.cursor
            pd.testing.assert_frame_equal(g.df, w.df, check_freq=False)
            assert list(g.engine._equity) == pytest.approx(list(w.engine._equity))
            assert len(g.engine._completed_trades) == len(w.engine._completed_trades)


class TestNothingToDo:
    def test_no_bars_at_all(self):
        session = _session(["1m"])
        result = session.extend(pd.DataFrame())
        assert result["added"] == 0
        assert "no bars" in result["reason"]

    def test_none_is_tolerated(self):
        session = _session(["1m"])
        assert session.extend(None)["added"] == 0

    def test_re_supplying_the_same_bars_changes_nothing(self):
        session = _session(["1m"])
        for _ in range(30):
            session.tick()
        result = session.extend(session._source_df.copy())
        assert result["added"] == 0
        # Not an error condition -- a poll that finds nothing new is the normal
        # case between bar closes, so there is nothing to report.
        assert result["reason"] is None

    def test_an_overlapping_batch_counts_only_what_is_new(self):
        session = _session(["1m"])
        _drain(session)
        overlap = pd.concat([session._source_df.iloc[-10:], _next_bars(session, 4)])
        assert session.extend(overlap)["added"] == 4


class TestReporting:
    def test_counts_and_totals_come_back(self):
        session = _session(["1m", "5m"])
        _drain(session)
        result = session.extend(_next_bars(session, 20))
        assert result["total_ticks"] == session.total_ticks
        assert result["bar_counts"] == session.bar_counts()
        assert result["bar_counts"]["5m"] == len(session.panes["5m"].stamps)

    def test_last_source_time_tracks_the_data_edge_not_the_replay(self):
        session = _session(["1m"], bars=60)
        assert session.last_source_time == pd.Timestamp("2026-01-05 10:29")
        # Nothing played yet, so there is no market time at all -- but the data
        # edge is already known. This is the gap a live follow is closing.
        assert session.market_time is None

        session.extend(_next_bars(session, 5))
        assert session.last_source_time == pd.Timestamp("2026-01-05 10:34")

    def test_reset_replays_the_extended_data(self):
        session = _session(["1m"], bars=60)
        _drain(session)
        session.extend(_next_bars(session, 10))
        session.reset()

        assert session._clock_index == 0
        assert session.total_ticks == 70
        _drain(session)
        assert session.total_ticks == 70
