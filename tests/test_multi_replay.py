"""
Tests for the multi-timeframe replay clock.

The property that matters is SYNCHRONISATION: every pane must always be
showing the same moment in market time. The naive implementation (step every
engine once per tick) satisfies "all panes advance" while completely failing
that property, so these tests assert market time, not bar counts.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.backtesting.multi_replay import (
    MultiReplaySession, TF_MINUTES, resample_ohlcv,
)
from src.strategies.ma_crossover import MACrossoverStrategy


def _minute_bars(count: int = 480, start=datetime(2026, 1, 5, 9, 30)) -> pd.DataFrame:
    """`count` one-minute bars with a gently trending price."""
    idx = pd.DatetimeIndex([start + timedelta(minutes=i) for i in range(count)])
    close = [4500 + (i % 37) * 0.25 + i * 0.01 for i in range(count)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 1.0 for c in close],
            "low": [c - 1.0 for c in close],
            "close": close,
            "volume": [100 + (i % 11) for i in range(count)],
        },
        index=idx,
    )


def _session(timeframes, bars=480):
    return MultiReplaySession(
        df=_minute_bars(bars),
        timeframes=timeframes,
        strategy_factory=lambda: MACrossoverStrategy(fast=9, slow=21),
        symbol="ES",
    )


class TestResampling:
    def test_aggregates_to_the_requested_timeframe(self):
        df = _minute_bars(60)
        out = resample_ohlcv(df, "5m")
        assert len(out) == 12
        # OHLC semantics: first open, max high, min low, last close, summed volume
        assert out.iloc[0]["open"] == df.iloc[0]["open"]
        assert out.iloc[0]["high"] == df.iloc[0:5]["high"].max()
        assert out.iloc[0]["low"] == df.iloc[0:5]["low"].min()
        assert out.iloc[0]["close"] == df.iloc[4]["close"]
        assert out.iloc[0]["volume"] == df.iloc[0:5]["volume"].sum()

    def test_rejects_an_unknown_timeframe(self):
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            resample_ohlcv(_minute_bars(10), "3m")


class TestClockSynchronisation:
    """The core property: all panes show the same market moment."""

    def test_every_advanced_pane_reports_the_same_market_time(self):
        s = _session(["1m", "5m", "15m", "1h"])
        checked = 0
        while not s.is_done:
            advanced = s.tick()
            now = s.market_time
            for tf, frame in advanced.items():
                # A pane's newest bar may open before `now` (a 1h bar opens up
                # to 59 minutes earlier) but must never open AFTER it -- that
                # would mean the pane had run ahead of the clock.
                assert frame.bar.timestamp <= now, (
                    f"{tf} pane ran ahead of the clock: {frame.bar.timestamp} > {now}"
                )
                # ...and must be within one of its own bars of the clock.
                lag = (now - frame.bar.timestamp).total_seconds() / 60
                assert lag < TF_MINUTES[tf], f"{tf} pane lagged {lag}min behind the clock"
                checked += 1
        assert checked > 0

    def test_coarse_panes_advance_proportionally_less_often(self):
        s = _session(["1m", "5m", "1h"])
        counts = {"1m": 0, "5m": 0, "1h": 0}
        while not s.is_done:
            for tf in s.tick():
                counts[tf] += 1
        # 480 one-minute bars -> 480 / 96 / 8
        assert counts["1m"] == 480
        assert counts["5m"] == 96
        assert counts["1h"] == 8

    def test_naive_implementation_would_desync(self):
        # Documents what the shared clock prevents. Stepping each engine once
        # per tick puts the 1h pane 60x further through market time than the
        # 1m pane; this asserts the real session does NOT behave that way.
        s = _session(["1m", "1h"])
        for _ in range(8):
            s.tick()
        m1 = s.panes["1m"].engine
        h1 = s.panes["1h"].engine
        assert m1.progress[0] == 8, "base pane should advance one bar per tick"
        assert h1.progress[0] == 0, "1h pane should not have completed a bar after 8 minutes"

    def test_one_tick_equals_one_base_bar(self):
        s = _session(["5m", "15m"], bars=300)
        # base is the finest SELECTED timeframe, not the source resolution
        assert s.base_timeframe == "5m"
        assert s.total_ticks == len(s.panes["5m"].stamps)


class TestSingleTimeframeStillWorks:
    """Requirement: selecting one timeframe must behave as before."""

    def test_single_timeframe_advances_every_tick(self):
        s = _session(["5m"])
        assert s.base_timeframe == "5m"
        ticks = 0
        while not s.is_done:
            advanced = s.tick()
            assert list(advanced) == ["5m"], "the only pane must advance on every tick"
            ticks += 1
        assert ticks == s.total_ticks


class TestIndependence:
    def test_each_pane_has_its_own_strategy_instance(self):
        s = _session(["1m", "5m", "1h"])
        strategies = [p.engine.strategy for p in s.panes.values()]
        assert len({id(x) for x in strategies}) == 3, "panes must not share strategy state"

    def test_each_pane_has_its_own_broker(self):
        s = _session(["1m", "5m"])
        for _ in range(120):
            if s.is_done:
                break
            s.tick()
        brokers = [p.engine._broker for p in s.panes.values()]
        assert len({id(b) for b in brokers}) == 2

    def test_panes_are_ordered_fine_to_coarse(self):
        s = _session(["1h", "1m", "15m", "5m"])
        assert s.timeframes == ["1m", "5m", "15m", "1h"]


class TestLifecycle:
    def test_reset_returns_every_pane_to_the_start(self):
        s = _session(["1m", "5m"])
        for _ in range(50):
            s.tick()
        assert s.progress()[0] == 50
        s.reset()
        assert s.progress()[0] == 0
        assert s.market_time is None
        for pane in s.panes.values():
            assert pane.cursor == 0
            assert pane.engine.progress[0] == 0

    def test_tick_past_the_end_raises(self):
        s = _session(["1m"], bars=10)
        while not s.is_done:
            s.tick()
        with pytest.raises(StopIteration):
            s.tick()

    def test_rejects_empty_input(self):
        with pytest.raises(ValueError, match="At least one timeframe"):
            MultiReplaySession(_minute_bars(10), [], lambda: MACrossoverStrategy(), "ES")
        with pytest.raises(ValueError, match="No market data"):
            MultiReplaySession(pd.DataFrame(), ["1m"], lambda: MACrossoverStrategy(), "ES")

    def test_rejects_unknown_timeframe(self):
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            _session(["1m", "3m"])


class TestEmissionInvariant:
    """
    The precise contract, stated once so it cannot drift.

    market_time is the OPEN of the current base bar, and the engine consumes
    that bar, so the effective clock is market_time + base. A pane emits its
    bar (open B, timeframe T) exactly when B + T <= clock -- on CLOSE, never on
    open. Emitting on open would hand the pane's strategy a bar whose
    high/low/close are still in the future.

    Two throwaway verification scripts got this wrong in opposite directions
    before it was pinned here, so both halves are asserted.
    """

    @pytest.mark.parametrize("timeframes", [
        ["1m", "5m"],
        ["1m", "5m", "15m"],
        ["5m", "15m", "1h"],
        ["1m", "5m", "15m", "30m", "1h"],
    ])
    def test_every_pane_sits_exactly_one_closed_bar_behind_the_clock(self, timeframes):
        s = _session(timeframes)
        base = pd.Timedelta(minutes=TF_MINUTES[s.base_timeframe])
        newest: dict[str, pd.Timestamp] = {}
        checks = 0

        while not s.is_done:
            advanced = s.tick()
            for tf, frame in advanced.items():
                newest[tf] = pd.Timestamp(frame.bar.timestamp)
            clock = pd.Timestamp(s.market_time) + base

            for tf, b in newest.items():
                t = pd.Timedelta(minutes=TF_MINUTES[tf])
                # the emitted bar has genuinely closed...
                assert b + t <= clock, (
                    f"{tf} bar {b} emitted before it closed (clock {clock}) — look-ahead"
                )
                # ...and the next one has not, so no pane is running late
                assert b + 2 * t > clock, (
                    f"{tf} bar {b} is stale at clock {clock} — pane fell behind"
                )
                checks += 1
        assert checks > 100

    def test_no_pane_ever_emits_a_bar_opening_after_the_clock(self):
        # The blunt look-ahead check: a bar whose OPEN is in the future can
        # never be legitimate, whatever the timeframe.
        s = _session(["1m", "5m", "15m", "1h"])
        while not s.is_done:
            for tf, frame in s.tick().items():
                assert pd.Timestamp(frame.bar.timestamp) <= pd.Timestamp(s.market_time), (
                    f"{tf} emitted a bar opening after the clock"
                )


def _pane_state(session, tf):
    """Everything about a pane that must not depend on WHEN it was added."""
    pane = session.panes[tf]
    engine = pane.engine
    return {
        "cursor": pane.cursor,
        "bars": len(pane.df),
        "trades": len(engine._completed_trades),
        "pnls": [round(t.pnl, 6) for t in engine._completed_trades],
        "last_stamp": str(pane.stamps[pane.cursor - 1]) if pane.cursor else None,
        "last_close": float(pane.df.iloc[pane.cursor - 1].close) if pane.cursor else None,
    }


class TestAddTimeframeMidSession:
    """
    A timeframe selected part-way through a session must be INDISTINGUISHABLE
    from one that was there all along.

    That is the whole correctness argument for letting the user re-tick the
    boxes mid-playback: if a late-added pane could differ by even one bar, the
    grid would stop showing one shared moment in the market, which is the
    property the shared clock exists to guarantee.
    """

    @pytest.mark.parametrize("ticks", [1, 7, 60, 123, 400])
    def test_added_pane_identical_to_one_present_from_the_start(self, ticks):
        from_start = _session(["1m", "5m", "15m"])
        for _ in range(ticks):
            from_start.tick()

        added_late = _session(["1m"])
        for _ in range(ticks):
            added_late.tick()
        added_late.add_timeframes(["5m", "15m"])

        for tf in ("5m", "15m"):
            assert _pane_state(added_late, tf) == _pane_state(from_start, tf), (
                f"{tf} added at tick {ticks} differs from one present from tick 0"
            )

    @pytest.mark.parametrize("ticks", [1, 60, 400])
    def test_adding_does_not_perturb_the_existing_panes(self, ticks):
        session = _session(["1m"])
        for _ in range(ticks):
            session.tick()
        before = _pane_state(session, "1m")
        clock_before = session.market_time

        session.add_timeframes(["15m"])

        assert _pane_state(session, "1m") == before
        assert session.market_time == clock_before

    def test_backfilled_pane_has_not_seen_an_unclosed_bar(self):
        """The look-ahead guard, restated for the catch-up path.

        _catch_up reuses tick()'s condition precisely so this holds; asserting
        it separately means a future edit to either one cannot quietly
        reintroduce the bug the emission invariant already caught once.
        """
        session = _session(["1m"])
        for _ in range(100):
            session.tick()
        clock = session.market_time

        session.add_timeframes(["15m"])
        pane = session.panes["15m"]

        assert pane.cursor > 0, "expected some 15m bars to have closed by tick 100"
        closes_at = pane.stamps[pane.cursor - 1] + pd.Timedelta(minutes=15)
        assert closes_at <= clock, (
            f"backfilled 15m pane emitted a bar closing {closes_at}, after the {clock} clock"
        )
        # ...and the NEXT bar must still be in the future.
        if not pane.is_done:
            next_closes = pane.stamps[pane.cursor] + pd.Timedelta(minutes=15)
            assert next_closes > clock

    def test_timeframe_finer_than_the_data_is_rejected_not_invented(self):
        """5m bars cannot be resampled down to 1m, so the request must fail loudly."""
        session = _session(["5m", "15m"])
        for _ in range(20):
            session.tick()

        result = session.add_timeframes(["1m", "30m"])

        assert result["rejected"] == ["1m"]
        assert result["added"] == ["30m"]
        assert "1m" not in session.panes

    def test_adding_a_timeframe_that_is_already_present_is_a_noop(self):
        session = _session(["1m", "5m"])
        for _ in range(50):
            session.tick()
        before = {tf: _pane_state(session, tf) for tf in session.timeframes}

        result = session.add_timeframes(["1m", "5m"])

        assert result == {"added": [], "rejected": [], "backfill": {}}
        assert {tf: _pane_state(session, tf) for tf in session.timeframes} == before

    def test_every_pane_is_still_emitted_after_an_addition(self):
        """Removal is a client-side filter, so tick() must never stop reporting
        a pane -- that is what makes re-showing one instant and in sync."""
        session = _session(["1m"])
        for _ in range(30):
            session.tick()
        session.add_timeframes(["5m"])

        seen = set()
        for _ in range(60):
            seen.update(session.tick())
        assert seen == {"1m", "5m"}

    def test_backfill_carries_the_bars_and_a_settling_frame(self):
        session = _session(["1m"])
        for _ in range(200):
            session.tick()
        result = session.add_timeframes(["15m"])
        bf = result["backfill"]["15m"]

        pane = session.panes["15m"]
        assert bf["bars_closed"] == pane.cursor
        assert len(bf["bars"]) == pane.cursor
        assert bf["truncated"] is False
        # The single frame settles every scalar, because FrameState carries the
        # completed-trade list cumulatively rather than as a delta.
        assert bf["frame"] is not None
        assert len(bf["frame"].completed_trades) == len(pane.engine._completed_trades)
        assert bf["bars"][-1]["t"] == pane.stamps[pane.cursor - 1].isoformat()

    def test_backfill_bar_cap_is_reported(self):
        session = _session(["1m"])
        for _ in range(300):
            session.tick()
        session.add_timeframes(["5m"])
        bf = session.backfill_of("5m", max_bars=10)

        assert len(bf["bars"]) == 10
        assert bf["bars_closed"] == session.panes["5m"].cursor > 10
        assert bf["truncated"] is True

    def test_adding_before_the_clock_starts_backfills_nothing(self):
        session = _session(["1m"])
        result = session.add_timeframes(["1h"])

        assert result["added"] == ["1h"]
        assert result["backfill"]["1h"]["bars_closed"] == 0
        assert result["backfill"]["1h"]["frame"] is None
        assert session.panes["1h"].cursor == 0

    def test_a_pane_added_late_survives_reset(self):
        session = _session(["1m"])
        for _ in range(100):
            session.tick()
        session.add_timeframes(["5m"])
        session.reset()

        assert "5m" in session.panes
        assert session.panes["5m"].cursor == 0
        assert session.market_time is None


NEW_TIMEFRAMES = ["10m", "20m", "25m", "35m", "40m", "45m"]


def _session_src(timeframes, source, bars=1200):
    """A session whose source resolution is stated explicitly."""
    return MultiReplaySession(
        df=_minute_bars(bars),
        timeframes=timeframes,
        strategy_factory=lambda: MACrossoverStrategy(fast=9, slow=21),
        symbol="ES",
        source_timeframe=source,
    )


class TestOddIntervalTimeframes:
    """
    10m / 20m / 25m / 35m / 40m / 45m.

    The previous five (1m, 5m, 15m, 30m, 1h) formed a divisibility chain, so the
    finest selected timeframe always divided every other one and could double as
    the frame everything was resampled from. 25m, 35m and 45m break that chain,
    and the failure is silent -- a 25m bar resampled from 15m bars holds 15 or 30
    minutes of trade, with the wrong high, low and volume. These tests pin the
    arithmetic rather than trusting it.
    """

    @pytest.mark.parametrize("tf", NEW_TIMEFRAMES)
    def test_every_resampled_bar_aggregates_exactly_its_own_minutes(self, tf):
        """Each bar must equal the aggregate of the source bars inside its bin.

        This is the test that would have caught the misalignment: it compares
        against the underlying 1-minute bars rather than against another
        resample, so a bin spanning the wrong amount of time cannot pass.
        """
        src = _minute_bars(1200)
        out = resample_ohlcv(src, tf)
        minutes = TF_MINUTES[tf]

        assert len(out) > 1, f"expected several {tf} bars from 1200 minutes"
        for stamp, bar in out.iterrows():
            window = src[(src.index >= stamp) & (src.index < stamp + pd.Timedelta(minutes=minutes))]
            assert not window.empty
            assert bar.open == window.open.iloc[0]
            assert bar.high == window.high.max()
            assert bar.low == window.low.min()
            assert bar.close == window.close.iloc[-1]
            assert bar.volume == window.volume.sum()

    @pytest.mark.parametrize("tf", NEW_TIMEFRAMES)
    def test_interior_bars_span_the_full_interval(self, tf):
        """Bars other than the edges must contain exactly `minutes` source bars.

        The first and last are allowed to be short: pandas anchors bins to the
        start of the day, so a session opening at 09:30 lands mid-bin for any
        interval that does not divide 570 minutes. That is pre-existing
        behaviour (1h has always done it) and it costs no correctness here --
        the bin's nominal close is what the clock compares against.
        """
        src = _minute_bars(1200)
        out = resample_ohlcv(src, tf)
        minutes = TF_MINUTES[tf]

        for stamp in out.index[1:-1]:
            window = src[(src.index >= stamp) & (src.index < stamp + pd.Timedelta(minutes=minutes))]
            assert len(window) == minutes, (
                f"{tf} bar at {stamp} spans {len(window)} minutes, expected {minutes}"
            )

    @pytest.mark.parametrize("timeframes", [
        ["1m", "10m", "25m"],
        ["5m", "25m", "45m"],
        ["1m", "35m"],
        ["10m", "20m", "40m"],
        ["5m", "20m", "35m", "45m"],
        ["1m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "40m", "45m", "1h"],
    ])
    def test_emission_invariant_holds_for_odd_intervals(self, timeframes):
        """The same contract as TestEmissionInvariant, over non-dividing sets."""
        source = "1m" if 1 in [TF_MINUTES[t] for t in timeframes] else "5m"
        s = _session_src(timeframes, source)
        base = pd.Timedelta(minutes=TF_MINUTES[s.base_timeframe])
        newest: dict[str, pd.Timestamp] = {}
        checks = 0

        while not s.is_done:
            advanced = s.tick()
            for tf, frame in advanced.items():
                newest[tf] = pd.Timestamp(frame.bar.timestamp)
            clock = pd.Timestamp(s.market_time) + base
            for tf, b in newest.items():
                t = pd.Timedelta(minutes=TF_MINUTES[tf])
                assert b + t <= clock, (
                    f"{tf} bar {b} emitted before it closed (clock {clock}) — look-ahead"
                )
                assert b + 2 * t > clock, (
                    f"{tf} bar {b} is stale against clock {clock} — pane running late"
                )
                checks += 1
        assert checks > 100

    @pytest.mark.parametrize("tf,expected_ratio", [
        ("10m", 10), ("20m", 20), ("25m", 25),
        ("35m", 35), ("40m", 40), ("45m", 45),
    ])
    def test_bar_count_ratio_against_the_one_minute_source(self, tf, expected_ratio):
        src = _minute_bars(1200)
        out = resample_ohlcv(src, tf)
        # 1200 minutes / ratio, +1 for the partial bin at each edge
        low = 1200 // expected_ratio
        assert low <= len(out) <= low + 2, (
            f"{tf}: {len(out)} bars from 1200 minutes, expected about {low}"
        )

    def test_a_source_that_does_not_divide_a_timeframe_is_refused(self):
        """The silent-corruption case, made loud.

        25m out of 15m bars is coarser but misaligned; without this guard the
        session would build it and every 25m bar would be wrong.
        """
        with pytest.raises(ValueError, match="whole multiple"):
            _session_src(["15m", "25m"], "15m")

    def test_default_source_still_works_for_the_dividing_chain(self):
        """No source given: the finest selected timeframe, as before."""
        s = _session(["5m", "15m", "30m"])
        assert s.source_timeframe == "5m"
        assert s.data_timeframe == "5m"

    def test_clock_base_is_the_finest_selected_not_the_source(self):
        """Playback speed must not change just because the source got finer."""
        s = _session_src(["10m", "25m"], "5m")
        assert s.source_timeframe == "5m"
        assert s.base_timeframe == "10m"
        # one tick per 10m bar, NOT one per 5m source bar
        assert s.total_ticks == len(s.panes["10m"].df)

    @pytest.mark.parametrize("ticks", [1, 13, 77])
    @pytest.mark.parametrize("late", ["25m", "35m", "45m"])
    def test_odd_timeframe_added_mid_session_matches_one_present_from_the_start(self, ticks, late):
        from_start = _session_src(["5m", late], "5m")
        for _ in range(ticks):
            from_start.tick()

        added = _session_src(["5m"], "5m")
        for _ in range(ticks):
            added.tick()
        result = added.add_timeframes([late])

        assert result["added"] == [late]
        assert _pane_state(added, late) == _pane_state(from_start, late)

    def test_adding_a_misaligned_timeframe_mid_session_is_rejected(self):
        """Source 15m, add 25m: coarser, but 25 % 15 != 0."""
        s = _session_src(["15m", "30m"], "15m")
        for _ in range(20):
            s.tick()

        result = s.add_timeframes(["25m", "45m", "1h"])

        assert result["rejected"] == ["25m"]
        assert result["added"] == ["45m", "1h"]
        assert "25m" not in s.panes

    def test_odd_panes_advance_at_the_right_cadence(self):
        """A 25m pane must move once per 25 minutes of market time, no more."""
        s = _session_src(["5m", "25m"], "5m")
        counts = {"5m": 0, "25m": 0}
        for _ in range(200):
            if s.is_done:
                break
            for tf in s.tick():
                counts[tf] += 1
        # 200 ticks x 5m = 1000 minutes -> 200 five-minute bars, 40 twenty-fives
        assert counts["5m"] == 200
        assert abs(counts["25m"] - 40) <= 1


class TestSourceTimeframeSelection:
    """
    The router picks the frame resolution. Two things must hold: it must divide
    every selected timeframe, and for the original five it must come out exactly
    as before, so no existing session starts fetching different data.
    """

    def test_every_selection_fetches_one_minute(self):
        """
        This used to assert the opposite -- that each selection fetched the
        coarsest resolution dividing it, which for the original five was the
        finest selected one. That is the cheapest fetch that can build the bars,
        and it was correct for as long as bars were all that mattered.

        VWAP needs the price distribution INSIDE each bar, which a source equal
        to the pane's own resolution cannot supply, so the same closed bar came
        back with a different VWAP depending on what else was ticked: 30m alone
        gave 7810.2336 where 1m + 30m gave 7809.9279. The fetch is now always 1m.
        """
        from itertools import combinations
        from api.routers.replay import _source_timeframe

        original = ["1m", "5m", "15m", "30m", "1h"]
        for n in range(1, len(original) + 1):
            for combo in combinations(original, n):
                assert _source_timeframe(list(combo)) == "1m", (
                    f"{combo} fetches {_source_timeframe(list(combo))}; any pane at "
                    f"that resolution has no minutes inside its bars"
                )

    @pytest.mark.parametrize("timeframes", [
        ["10m", "25m"], ["35m", "45m"], ["25m"], ["45m"], ["20m", "40m"],
        ["1m", "10m", "25m"], ["5m", "20m", "35m", "45m"],
        ["1m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "40m", "45m", "1h"],
    ])
    def test_chosen_source_divides_every_selected_timeframe(self, timeframes):
        from api.routers.replay import _source_timeframe

        src = _source_timeframe(timeframes)
        for tf in timeframes:
            assert TF_MINUTES[tf] % TF_MINUTES[src] == 0, (
                f"source {src} does not divide {tf}; resampled bars would misalign"
            )

    @pytest.mark.parametrize("timeframes", [
        ["10m", "25m"], ["1m", "10m", "25m"], ["5m", "25m", "45m"], ["45m"],
    ])
    def test_the_chosen_source_actually_builds_a_working_session(self, timeframes):
        from api.routers.replay import _source_timeframe

        s = _session_src(timeframes, _source_timeframe(timeframes))
        for _ in range(50):
            if s.is_done:
                break
            s.tick()
        assert s.base_timeframe == min(timeframes, key=lambda t: TF_MINUTES[t])
        for tf in timeframes:
            assert tf in s.panes


class TestStrategyParamDefaults:
    """
    `params: {}` is the documented default for the API field and a reasonable
    way to say "use the defaults". It used to raise KeyError inside the strategy
    constructor and surface as a bare 500.
    """

    def test_empty_params_uses_registry_defaults(self):
        from api.strategy_registry import build_strategy, STRATEGIES

        for spec in STRATEGIES:
            built = build_strategy(spec["id"], {})
            assert built is not None, f"{spec['id']} could not be built from empty params"

    def test_partial_params_keeps_the_supplied_value(self):
        from api.strategy_registry import build_strategy

        s = build_strategy("rsi_divergence", {"rsi_overbought": 88})
        assert s.rsi_overbought == 88     # supplied
        assert s.rsi_oversold == 2        # defaulted
        assert s.swing_lookback == 5      # defaulted

    def test_unknown_strategy_still_raises_a_clear_error(self):
        from api.strategy_registry import build_strategy

        with pytest.raises(ValueError, match="Unknown strategy id"):
            build_strategy("does_not_exist", {})
