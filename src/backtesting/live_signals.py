"""Live strategy signals (upgrade plan, Feature 2).

A run on live data used to move only its candles: the entry and exit markers were the
backtest's, and the strategy never saw a bar that printed after the run. This runner
keeps the run's strategy going on those bars.

  * CLOSED BARS ONLY. The newest bar of a live series is still forming; it is never fed,
    so a signal can never appear and then vanish or move as that bar changes.
  * THE ENGINE'S RULES. A signal counts when the engine would act on it (BUY when flat
    or short, SELL when flat or long, CLOSE when in a position), with the position the
    signals themselves imply -- what the engine's broker holds after each fill.
  * CATCH-UP ONCE. On first use the strategy is replayed over the run's bars, so its
    state (and position) is exactly what the backtest's was; after that each new closed
    bar is one on_bar() call.

Signals before `edge` (the run's last bar when it was made) are the backtest's own and
are not reported; from the edge on they are live.

shortcut: signals live in memory with the run, as the run itself does; a table
(live_signals in the plan) is needed only if a history must outlive a server restart.
"""
from __future__ import annotations

import threading
from datetime import datetime

import pandas as pd

from src.data.base_provider import DataProvider
from src.strategies.base_strategy import BaseStrategy, SignalType


class LiveSignalRunner:
    def __init__(self, strategy: BaseStrategy, symbol: str, timeframe: str,
                 contracts: int = 1, edge: datetime | None = None):
        self.strategy = strategy
        self.symbol, self.timeframe, self.contracts = symbol, timeframe, contracts
        self.edge = edge
        self.position = 0
        self.fed_until: pd.Timestamp | None = None
        self.signals: list[dict] = []
        self._lock = threading.Lock()          # two tabs polling one run must not feed a bar twice
        self.failed: str | None = None
        strategy.reset()

    def feed(self, df: pd.DataFrame) -> list[dict]:
        """Run the strategy on every closed bar of `df` not yet seen (all but the newest,
        which is still forming). Returns the signals this call added."""
        with self._lock:
            return self._feed(df)

    def try_feed(self, df: pd.DataFrame) -> None:
        """feed(), unless a feed is already running (the catch-up, or another tab's poll):
        then nothing -- fed_until means the next poll picks up every bar this one skipped."""
        if self._lock.acquire(blocking=False):
            try:
                self._feed(df)
            finally:
                self._lock.release()

    def catch_up_in_background(self, df: pd.DataFrame) -> threading.Thread:
        """Replay the run's bars off the request thread: 6,900 one-minute bars take ~25 s,
        and the chart's poll must not wait for them. A failure switches signals off."""
        def run():
            try:
                self.feed(df)
            except Exception as exc:              # a strategy bug must not reach the chart
                self.failed = str(exc)
        t = threading.Thread(target=run, name="live-signals-catch-up", daemon=True)
        t.start()
        return t

    def _feed(self, df: pd.DataFrame) -> list[dict]:
        if self.failed:
            return []
        closed = df.iloc[:-1]
        if self.fed_until is not None:
            closed = closed[closed.index > self.fed_until]
        added = []
        for bar in DataProvider.df_to_bars(closed, self.symbol, self.timeframe):
            sig = self.strategy.on_bar(df.loc[: bar.timestamp], bar, self.position)
            if sig is not None and self._acts(sig.signal_type):
                if self.edge is None or bar.timestamp >= self.edge:
                    added.append({"time": bar.timestamp, "side": sig.signal_type.value,
                                  "price": float(sig.price), "reason": sig.reason})
        if len(closed):
            self.fed_until = closed.index[-1]
        self.signals.extend(added)
        return added

    def _acts(self, kind: SignalType) -> bool:
        if kind == SignalType.BUY and self.position <= 0:
            self.position = self.contracts
        elif kind == SignalType.SELL and self.position >= 0:
            self.position = -self.contracts
        elif kind == SignalType.CLOSE and self.position != 0:
            self.position = 0
        else:
            return False
        return True
