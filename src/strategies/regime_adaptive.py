"""Regime-adaptive strategy: auto-switches trading logic based on the current
market regime (src/analysis/regime.py).

Mapping:
  trending_up / trending_down -> trend-following (be long/short with the trend)
  sideways                    -> RSI Mean Reversion (fade extremes)
  high_volatility             -> Breakout          (ride the expansion)

The trending branch is state-based (are we above/below the trend), not
edge-triggered on the EMA crossover. That's a deliberate choice, not a
simplification for its own sake: by construction, trend_strength = (fast EMA
- slow EMA) / ATR is near zero exactly AT the crossover -- so the bar where a
real crossover happens is always classified "sideways", and an edge-triggered
MA-crossover strategy would silently miss every single entry (confirmed by
testing: wrapping MACrossoverStrategy this way produced zero trades over a
3000-bar run where it alone produced 87). State-based entry sidesteps that.

Honesty: switching regimes mid-trade means the newly-active sub-strategy has
no memory of an open position's context (e.g. Breakout's trailing stop is
cleared when handing off to it). Position sizing/direction stays engine-
managed and continuous; only the entry/exit LOGIC hands off between regimes.
"""

from typing import Optional
import pandas as pd

from .base_strategy import BaseStrategy, Signal, SignalType
from .rsi_mean_reversion import RSIMeanReversionStrategy
from .breakout import BreakoutStrategy
from ..data.base_provider import Bar
from ..analysis.regime import classify_regime


class RegimeAdaptiveStrategy(BaseStrategy):
    def __init__(
        self,
        trend_fast: int = 9,
        trend_slow: int = 21,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        breakout_lookback: int = 20,
        breakout_atr_mult: float = 2.0,
    ):
        super().__init__(name="Regime_Adaptive")
        self.trend_fast = trend_fast
        self.trend_slow = trend_slow
        self._sideways = RSIMeanReversionStrategy(rsi_period, rsi_oversold, rsi_overbought)
        self._breakout = BreakoutStrategy(breakout_lookback, atr_mult=breakout_atr_mult)
        self._active_key: Optional[str] = None
        self.regime_log: list[tuple] = []

    def reset(self):
        self._active_key = None
        self.regime_log = []
        self._sideways.reset()
        self._breakout.reset()

    def on_bar(self, bars_df: pd.DataFrame, current_bar: Bar, position: int) -> Optional[Signal]:
        detail = classify_regime(bars_df, fast=self.trend_fast, slow=self.trend_slow)
        regime = detail["regime"]
        self.regime_log.append((current_bar.timestamp, regime, detail["trend_strength"], detail["vol_ratio"]))

        if regime == "insufficient_data":
            return None

        if regime != self._active_key:
            # Only reset the sub-strategy actually holding state for that regime.
            if regime == "sideways":
                self._sideways.reset()
            elif regime == "high_volatility":
                self._breakout.reset()
            self._active_key = regime

        if regime in ("trending_up", "trending_down"):
            if regime == "trending_up" and position <= 0:
                return Signal(
                    signal_type=SignalType.BUY,
                    strategy_name=self.name,
                    timestamp=current_bar.timestamp,
                    price=current_bar.close,
                    reason=f"[trending_up] EMA{self.trend_fast} above EMA{self.trend_slow}",
                )
            if regime == "trending_down" and position >= 0:
                return Signal(
                    signal_type=SignalType.SELL,
                    strategy_name=self.name,
                    timestamp=current_bar.timestamp,
                    price=current_bar.close,
                    reason=f"[trending_down] EMA{self.trend_fast} below EMA{self.trend_slow}",
                )
            return None

        sub = self._sideways if regime == "sideways" else self._breakout
        signal = sub.on_bar(bars_df, current_bar, position)
        if signal is not None:
            signal = Signal(
                signal_type=signal.signal_type,
                strategy_name=self.name,
                timestamp=signal.timestamp,
                price=signal.price,
                reason=f"[{regime}] {signal.reason}",
            )
        return signal
