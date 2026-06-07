"""Donchian Channel breakout strategy (common in futures trend-following)."""

from typing import Optional
import pandas as pd

from .base_strategy import BaseStrategy, Signal, SignalType
from ..data.base_provider import Bar


class BreakoutStrategy(BaseStrategy):
    """
    Buy when price breaks above the N-bar high.
    Sell when price breaks below the N-bar low.
    Exit via an ATR-based trailing stop or a reverse signal.

    Parameters
    ----------
    lookback    : bars to look back for high/low channel (default 20)
    atr_period  : ATR period for stop calculation (default 14)
    atr_mult    : stop distance = atr_mult * ATR (default 2.0)
    """

    def __init__(self, lookback: int = 20, atr_period: int = 14, atr_mult: float = 2.0):
        super().__init__(name=f"Breakout_{lookback}")
        self.lookback = lookback
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self._stop_price: Optional[float] = None

    def reset(self):
        self._stop_price = None

    def on_bar(self, bars_df: pd.DataFrame, current_bar: Bar, position: int) -> Optional[Signal]:
        if len(bars_df) < max(self.lookback, self.atr_period) + 2:
            return None

        # Exclude current bar from channel so we don't look ahead
        prior = bars_df.iloc[-(self.lookback + 1):-1]
        channel_high = prior["high"].max()
        channel_low = prior["low"].min()
        atr = self._calc_atr(bars_df, self.atr_period)

        c = current_bar.close

        # Manage existing stop
        if position > 0 and self._stop_price is not None:
            trailing = c - self.atr_mult * atr
            self._stop_price = max(self._stop_price, trailing)
            if c <= self._stop_price:
                hit_price = self._stop_price
                self._stop_price = None
                return Signal(
                    signal_type=SignalType.CLOSE,
                    strategy_name=self.name,
                    timestamp=current_bar.timestamp,
                    price=c,
                    reason=f"Long stop hit @ {hit_price:.2f}",
                )

        if position < 0 and self._stop_price is not None:
            trailing = c + self.atr_mult * atr
            self._stop_price = min(self._stop_price, trailing)
            if c >= self._stop_price:
                hit_price = self._stop_price
                self._stop_price = None
                return Signal(
                    signal_type=SignalType.CLOSE,
                    strategy_name=self.name,
                    timestamp=current_bar.timestamp,
                    price=c,
                    reason=f"Short stop hit @ {hit_price:.2f}",
                )

        # Breakout entries
        if c > channel_high and position <= 0:
            self._stop_price = c - self.atr_mult * atr
            return Signal(
                signal_type=SignalType.BUY,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=c,
                reason=f"Broke above {channel_high:.2f} (channel high)",
            )

        if c < channel_low and position >= 0:
            self._stop_price = c + self.atr_mult * atr
            return Signal(
                signal_type=SignalType.SELL,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=c,
                reason=f"Broke below {channel_low:.2f} (channel low)",
            )

        return None

    @staticmethod
    def _calc_atr(df: pd.DataFrame, period: int) -> float:
        h, l, c = df["high"], df["low"], df["close"]
        prev_c = c.shift(1)
        tr = pd.concat([
            h - l,
            (h - prev_c).abs(),
            (l - prev_c).abs(),
        ], axis=1).max(axis=1)
        return float(tr.ewm(span=period, adjust=False).mean().iloc[-1])
