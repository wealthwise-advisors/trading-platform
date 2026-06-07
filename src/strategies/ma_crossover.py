"""Moving Average Crossover strategy (fast MA crosses above/below slow MA)."""

from typing import Optional
import pandas as pd

from .base_strategy import BaseStrategy, Signal, SignalType
from ..data.base_provider import Bar


class MACrossoverStrategy(BaseStrategy):
    """
    Long when fast EMA > slow EMA.
    Short when fast EMA < slow EMA.

    Parameters
    ----------
    fast : int   — fast EMA period (default 9)
    slow : int   — slow EMA period (default 21)
    """

    def __init__(self, fast: int = 9, slow: int = 21):
        super().__init__(name=f"MA_Cross_{fast}_{slow}")
        self.fast = fast
        self.slow = slow
        self._prev_fast: Optional[float] = None
        self._prev_slow: Optional[float] = None

    def reset(self):
        self._prev_fast = None
        self._prev_slow = None

    def on_bar(self, bars_df: pd.DataFrame, current_bar: Bar, position: int) -> Optional[Signal]:
        if len(bars_df) < self.slow + 1:
            return None

        closes = bars_df["close"]
        fast_ema = closes.ewm(span=self.fast, adjust=False).mean()
        slow_ema = closes.ewm(span=self.slow, adjust=False).mean()

        curr_fast = fast_ema.iloc[-1]
        curr_slow = slow_ema.iloc[-1]
        prev_fast = fast_ema.iloc[-2]
        prev_slow = slow_ema.iloc[-2]

        # Golden cross: fast crosses above slow
        if prev_fast <= prev_slow and curr_fast > curr_slow and position <= 0:
            return Signal(
                signal_type=SignalType.BUY,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_bar.close,
                reason=f"EMA{self.fast} crossed above EMA{self.slow}",
            )

        # Death cross: fast crosses below slow
        if prev_fast >= prev_slow and curr_fast < curr_slow and position >= 0:
            return Signal(
                signal_type=SignalType.SELL,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_bar.close,
                reason=f"EMA{self.fast} crossed below EMA{self.slow}",
            )

        return None
