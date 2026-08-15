"""
Multi-timeframe replay: several ReplayEngine instances advanced off ONE
shared market clock.

WHY A SHARED CLOCK RATHER THAN N INDEPENDENT ENGINES
-----------------------------------------------------
The obvious implementation -- keep N ReplayEngine instances and call step()
on all of them once per tick -- does not produce a synchronised view. step()
advances one BAR, and a bar means a different amount of market time per
timeframe. After 100 ticks a 1m pane has advanced 100 minutes while a 1h pane
has advanced 100 hours; the panes would be showing different days and the
"synced grid" would be meaningless.

So the clock is measured in MARKET TIME, not in bars:

    * the finest selected timeframe is the base; one tick advances market
      time by exactly one base bar
    * every other timeframe steps only when market time reaches the close of
      its next bar

At any instant every pane is therefore showing the same moment in the market,
and coarser panes simply update less often -- which is exactly how a real
multi-timeframe terminal behaves. A 1m/5m/1h grid advances its 5m pane every
5th tick and its 1h pane every 60th.

WHY THE SOURCE RESOLUTION IS NOT SIMPLY THE FINEST SELECTED TIMEFRAME
---------------------------------------------------------------------
Every pane is a resample of one source frame, and resampling is only faithful
when the source resolution DIVIDES the target. The original timeframes formed a
divisibility chain (1 | 5 | 15 | 30 | 60), so the finest selected one divided
all the others and could double as the source. Values like 25m and 35m break
that: resampling a 15m frame to 25m groups 15m bars by which 25m bin their left
edge falls in, so a "25m bar" ends up holding 15 or 30 minutes of trade --
wrong high, wrong low, wrong volume, and silently so.

So `source_timeframe` is passed in separately and every selected timeframe must
be a whole multiple of it (the caller picks the greatest common divisor; see
api/routers/replay.py::_source_timeframe). The CLOCK base is still the finest
selected timeframe, so tick counts and playback speed are unchanged -- only the
frame the panes are built from got finer.

CHANGING THE TIMEFRAME SET MID-SESSION
--------------------------------------
The source frame is loaded once, at the resolution described above, and that
resolution is fixed for the session's lifetime. Two consequences, and they are
not symmetric:

  * a timeframe that is a whole MULTIPLE of the source resolution can be added
    at any moment -- it is a deterministic resample of data already in memory,
    so its whole history up to the current clock is reproducible exactly. It is
    backfilled by stepping a fresh engine under the same emission condition
    tick() uses, so it lands precisely where it would have been had it existed
    from the start, with no look-ahead.

  * anything else cannot be added at all -- neither a finer timeframe (1m out of
    a 5m frame would invent bars that never existed) nor a coarser one the
    source does not divide (25m out of a 15m frame would misalign, per above).
    Those need a refetch, i.e. a new session, and add_timeframes reports them as
    `rejected` rather than fabricating data.

Removing a timeframe is deliberately NOT a server-side operation. Every pane
keeps being stepped and emitted, and the client simply stops rendering the row.
That costs almost nothing -- a tick only carries the panes that actually closed
a bar, and the base pane has to be stepped anyway because it IS the clock -- and
it buys two things worth more than the bandwidth: re-showing a timeframe is
instant and exactly in sync (its state was never allowed to go stale), and no
backend state is created or destroyed mid-tick, so the shared clock cannot be
perturbed by a UI toggle.

Each timeframe gets its OWN strategy instance and its own paper broker.
Strategies are stateful (RSI divergence arms a setup across bars), so sharing
one instance across timeframes would let a 1h bar corrupt the 1m strategy's
pre-condition state. The engines are deliberately independent in every respect
except the clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from ..strategies.base_strategy import BaseStrategy
from .replay_engine import FrameState, ReplayEngine

# Bar aggregation lives in ONE module now (src/data/resample.py). It used to be
# duplicated here, in ExternalCSVProvider and inline in SchwabDataProvider.load,
# and the copy that was never session-anchored kept reintroducing shifted bars on
# whichever path happened to reach it. Re-exported because callers and tests
# already import these names from here.
from src.data.resample import (  # noqa: E402,F401
    bar_anchor,
    OHLCV_AGG as _OHLCV_AGG,  # re-exported: tests and callers import it from here
    TF_ALIAS,
    TF_MINUTES,
    resample_ohlcv,
    session_origin,
)

__all__ = ["TF_MINUTES", "TF_ALIAS", "session_origin", "resample_ohlcv",
           "MultiReplaySession", "TimeframePane"]


@dataclass
class TimeframePane:
    """One timeframe's engine plus the bookkeeping the clock needs."""
    timeframe: str
    engine: ReplayEngine
    df: pd.DataFrame
    #: index of the next bar this pane will emit
    cursor: int = 0
    #: timestamps of this pane's bars, cached for the clock comparison
    stamps: list = field(default_factory=list)

    @property
    def is_done(self) -> bool:
        return self.cursor >= len(self.stamps)


class MultiReplaySession:
    """
    Drives several timeframes of the same instrument in lockstep.

    Usage:
        session = MultiReplaySession(base_df, ["1m", "5m", "1h"], make_strategy, ...)
        while not session.is_done:
            advanced = session.tick()      # {timeframe: FrameState} for panes that moved
    """

    def __init__(
        self,
        df: pd.DataFrame,
        timeframes: list[str],
        strategy_factory: Callable[[], BaseStrategy],
        symbol: str,
        initial_capital: float = 100_000.0,
        commission_per_contract: float = 2.50,
        slippage_ticks: int = 1,
        tick_size: float = 0.25,
        tick_value: float = 12.50,
        point_value: float = 50.0,
        contracts_per_trade: int = 1,
        session_start=None,
        source_timeframe: Optional[str] = None,
    ):
        if not timeframes:
            raise ValueError("At least one timeframe is required.")
        unknown = [t for t in timeframes if t not in TF_MINUTES]
        if unknown:
            raise ValueError(f"Unsupported timeframe(s): {unknown}")
        if df.empty:
            raise ValueError("No market data supplied to the replay session.")

        # Defaults to the finest selected timeframe, which is what the caller
        # used to pass implicitly. That is only a valid source when it divides
        # every other selection -- true of 1m/5m/15m/30m/1h, not of 25m or 35m.
        source_timeframe = source_timeframe or min(timeframes, key=lambda t: TF_MINUTES[t])
        if source_timeframe not in TF_MINUTES:
            raise ValueError(f"Unsupported source timeframe {source_timeframe!r}")
        src_min = TF_MINUTES[source_timeframe]
        misaligned = [t for t in timeframes if TF_MINUTES[t] % src_min != 0]
        if misaligned:
            raise ValueError(
                f"{misaligned} cannot be built from {source_timeframe} bars: each "
                f"timeframe must be a whole multiple of the source resolution, or "
                f"the resampled bars would span the wrong amount of market time."
            )
        self.source_timeframe = source_timeframe
        # Kept for the bin origin -- see resample_ohlcv. Every pane must tile
        # from the same session open or the panes disagree about where a bar
        # starts, which is worse than any single pane being wrong.
        self.session_start = session_start

        # Finest first, so the base pane is index 0 and the grid reads
        # fine -> coarse left to right.
        self.timeframes = sorted(set(timeframes), key=lambda t: TF_MINUTES[t])
        self.base_timeframe = self.timeframes[0]
        self.symbol = symbol
        self._source_df = df

        # Kept so a pane added later is built exactly like the originals.
        self._strategy_factory = strategy_factory
        self._engine_kwargs = dict(
            initial_capital=initial_capital,
            commission_per_contract=commission_per_contract,
            slippage_ticks=slippage_ticks,
            tick_size=tick_size,
            tick_value=tick_value,
            point_value=point_value,
            contracts_per_trade=contracts_per_trade,
            session_start=session_start,
        )

        self.panes: dict[str, TimeframePane] = {}
        for tf in self.timeframes:
            # The base timeframe uses the supplied frame as-is when the data is
            # already at (or coarser than) that resolution -- resampling 5m data
            # to "5m" is a no-op but resampling it to "1m" would invent bars.
            self.panes[tf] = self._build_pane(tf)

        # Bar durations, cached for the clock comparison in tick().
        self._deltas = {tf: pd.Timedelta(minutes=TF_MINUTES[tf]) for tf in self.timeframes}
        self._base_delta = self._deltas[self.base_timeframe]
        self._clock_index = 0

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    @property
    def _base(self) -> TimeframePane:
        return self.panes[self.base_timeframe]

    @property
    def total_ticks(self) -> int:
        """One tick per base-timeframe bar."""
        return len(self._base.stamps)

    @property
    def is_done(self) -> bool:
        return self._clock_index >= self.total_ticks

    @property
    def market_time(self) -> Optional[pd.Timestamp]:
        """The moment the whole grid is currently showing."""
        if self._clock_index == 0 or not self._base.stamps:
            return None
        return self._base.stamps[min(self._clock_index, self.total_ticks) - 1]

    def progress(self) -> tuple[int, int]:
        return self._clock_index, self.total_ticks

    def tick(self) -> dict[str, FrameState]:
        """
        Advance market time by one base bar.

        Returns only the panes that actually produced a new bar, so a 1h pane
        contributes nothing on 59 of every 60 ticks and the client can leave it
        untouched instead of redrawing it.
        """
        if self.is_done:
            raise StopIteration("Replay is complete.")

        now = self._base.stamps[self._clock_index]
        self._clock_index += 1
        # Market time after this base bar has been consumed. Bars are labelled
        # at their OPEN (closed="left", label="left"), so the bar stamped `now`
        # covers [now, now + base).
        clock = now + self._base_delta

        advanced: dict[str, FrameState] = {}
        for tf, pane in self.panes.items():
            # A pane emits its next bar only once that bar has CLOSED.
            #
            # Comparing against the bar's OPEN instead would hand the client a
            # bar whose high/low/close are still in the future -- at 09:30 the
            # 1h bar labelled 09:00 already "knows" the whole hour. That is
            # look-ahead, and it would also feed future prices to the pane's
            # strategy. Emitting on close costs one bar of latency on coarse
            # panes, which is the honest representation.
            while not pane.is_done and pane.stamps[pane.cursor] + self._deltas[tf] <= clock:
                frame = pane.engine.step()
                pane.cursor += 1
                advanced[tf] = frame        # keep only the latest within a tick

        return advanced

    def _build_pane(self, tf: str) -> TimeframePane:
        """A fresh pane for `tf`, resampled from the session's source frame."""
        # with_vwap_price: each output bar also carries its own
        # volume-weighted price, built from the source bars inside it, so
        # the pane's VWAP accumulates what a broker platform accumulates
        # rather than (H+L+C)/3. Collapses to (H+L+C)/3 when the source
        # and the pane are the same resolution.
        # bar_anchor, NOT session_start: bars tile from midnight on the
        # exchange's clock, while VWAP resets at the session open. Using one
        # anchor for both put 25m/35m/40m/45m on a grid no broker platform
        # uses -- see src/data/resample.bar_anchor.
        tf_df = resample_ohlcv(self._source_df, tf, bar_anchor(self.symbol),
                               with_vwap_price=True)
        engine = ReplayEngine(
            strategy=self._strategy_factory(),
            symbol=self.symbol,
            timeframe=tf,
            **self._engine_kwargs,
        )
        engine.load(tf_df)
        return TimeframePane(timeframe=tf, engine=engine, df=tf_df,
                             stamps=list(tf_df.index))

    def _catch_up(self, pane: TimeframePane):
        """
        Step a newly built pane forward to the current market clock, returning
        its final FrameState (None if nothing has closed yet).

        Uses the SAME condition as tick(), so the pane ends up exactly where it
        would have been had it been present from the first tick -- same bars,
        same strategy state, same fills -- and never sees a bar that has not
        closed yet. The clock is reconstructed from `_clock_index - 1` because
        tick() advances that index *before* comparing, so the last tick already
        issued is the one at index - 1.
        """
        if self._clock_index == 0:
            return None
        clock = self._base.stamps[self._clock_index - 1] + self._base_delta
        delta = self._deltas[pane.timeframe]
        last = None
        while not pane.is_done and pane.stamps[pane.cursor] + delta <= clock:
            last = pane.engine.step()
            pane.cursor += 1
        return last

    @property
    def data_timeframe(self) -> str:
        """
        Resolution the source frame holds. NOT the clock base: the clock still
        ticks once per finest-selected bar, but panes are resampled from this,
        so this is what decides which timeframes can be added mid-session.
        """
        return self.source_timeframe

    def add_timeframes(self, requested: list[str]) -> dict:
        """
        Bring extra timeframes into a running session.

        Add-only, on purpose: removal is the client's business (see the module
        docstring), so this never tears down a pane and can never disturb the
        clock. Timeframes already present are no-ops.

        Returns {"added": [...], "rejected": [...], "backfill": {tf: {...}}}.
        `rejected` lists timeframes that are not whole multiples of the source
        resolution -- they cannot be resampled out of the loaded frame without
        inventing or misaligning bars, so the caller has to start a new session.
        """
        src_min = TF_MINUTES[self.source_timeframe]
        want = [t for t in dict.fromkeys(requested) if t in TF_MINUTES]

        # A whole multiple of the source can be resampled faithfully; anything
        # else -- finer, or coarser but misaligned -- cannot.
        rejected = sorted((t for t in want if TF_MINUTES[t] % src_min != 0),
                          key=lambda t: TF_MINUTES[t])
        addable = sorted((t for t in want
                          if t not in self.panes and TF_MINUTES[t] % src_min == 0),
                         key=lambda t: TF_MINUTES[t])

        added, backfill = [], {}
        for tf in addable:
            pane = self._build_pane(tf)
            # Set before _catch_up -- it reads this pane's bar duration to
            # decide which of its bars have already closed.
            self._deltas[tf] = pd.Timedelta(minutes=TF_MINUTES[tf])
            last = self._catch_up(pane)
            self.panes[tf] = pane
            self.timeframes = sorted(self.panes, key=lambda t: TF_MINUTES[t])
            added.append(tf)
            backfill[tf] = self.backfill_of(tf, frame=last)

        return {"added": added, "rejected": rejected, "backfill": backfill}

    def backfill_of(self, tf: str, frame=None, max_bars: int = 500) -> dict:
        """
        The history a just-added pane needs to render as if it had always been
        there: its closed bars, plus the one frame that is its current state.

        Only the bars have to be replayed. FrameState carries position,
        portfolio value and the completed-trade list cumulatively, so the LAST
        frame alone settles every scalar -- which is why this returns a bar list
        and a single frame rather than every frame since the open.

        Each bar carries its OWN vwap and bands, though, because those are not
        cumulative in that sense -- they are a value per bar. Without them a
        timeframe added part-way through could be jumped to but every band
        column on its historical rows would be blank, which is most of the
        reason to jump to it. The engine already precomputed the whole series
        at load, so this is an index, not a recomputation.

        `frame` is handed back raw (a FrameState, or None if the pane has not
        closed a bar yet) rather than serialized -- the API layer owns the wire
        format, not this module.
        """
        pane = self.panes[tf]
        closed = pane.df.iloc[:pane.cursor]
        offset = 0
        if max_bars is not None and len(closed) > max_bars:
            offset = len(closed) - max_bars
            closed = closed.iloc[-max_bars:]
        return {
            "bars": [
                {"t": stamp.isoformat(), "o": float(row.open), "h": float(row.high),
                 "l": float(row.low), "c": float(row.close),
                 "v": None if pd.isna(row.volume) else float(row.volume),
                 **pane.engine.vwap_at(offset + i)}
                for i, (stamp, row) in enumerate(closed.iterrows())
            ],
            "bars_closed": int(pane.cursor),
            "truncated": int(pane.cursor) > len(closed),
            "frame": frame,
        }

    def reset(self):
        for pane in self.panes.values():
            pane.engine.reset()
            pane.engine.load(pane.df)
            pane.cursor = 0
        self._clock_index = 0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def bar_counts(self) -> dict[str, int]:
        return {tf: len(p.stamps) for tf, p in self.panes.items()}
