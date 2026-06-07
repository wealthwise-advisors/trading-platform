"""RSI mean-reversion strategy."""

from typing import Optional
import pandas as pd

from .base_strategy import BaseStrategy, Signal, SignalType
from ..data.base_provider import Bar


class RSIMeanReversionStrategy(BaseStrategy):
    """
    Buy when RSI crosses back above oversold level.
    Sell when RSI crosses back below overbought level.
    Close position when RSI returns to neutral zone.

    Parameters
    ----------
    period      : RSI period (default 14)
    oversold    : RSI level to go long (default 30)
    overbought  : RSI level to go short (default 70)
    neutral_low : exit long below this (default 50)
    neutral_high: exit short above this (default 50)
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        neutral: float = 50.0,
    ):
        super().__init__(name=f"RSI_MeanRev_{period}")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.neutral = neutral

    def reset(self):
        pass

    def on_bar(self, bars_df: pd.DataFrame, current_bar: Bar, position: int) -> Optional[Signal]:
        if len(bars_df) < self.period + 2:
            return None

        rsi = self._calc_rsi(bars_df["close"], self.period)
        curr_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # Cross back above oversold -> go long
        if prev_rsi <= self.oversold and curr_rsi > self.oversold and position <= 0:
            return Signal(
                signal_type=SignalType.BUY,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_bar.close,
                reason=f"RSI crossed above oversold {self.oversold}",
            )

        # Cross back below overbought -> go short
        if prev_rsi >= self.overbought and curr_rsi < self.overbought and position >= 0:
            return Signal(
                signal_type=SignalType.SELL,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_bar.close,
                reason=f"RSI crossed below overbought {self.overbought}",
            )

        # Exit long when RSI crosses neutral going down
        if position > 0 and prev_rsi >= self.neutral and curr_rsi < self.neutral:
            return Signal(
                signal_type=SignalType.CLOSE,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_bar.close,
                reason="RSI crossed below neutral — exit long",
            )

        # Exit short when RSI crosses neutral going up
        if position < 0 and prev_rsi <= self.neutral and curr_rsi > self.neutral:
            return Signal(
                signal_type=SignalType.CLOSE,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_bar.close,
                reason="RSI crossed above neutral — exit short",
            )

        return None

    @staticmethod
    def _calc_rsi(closes: pd.Series, period: int) -> pd.Series:
        delta = closes.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))
