"""
RSI Divergence Strategy
=======================
Based on strategy_original_first.py and strategy_six.py.

LONG  (BUY):  Price makes a new lower low while RSI(2) makes a higher low
              → RSI momentum is recovering even as price falls (bullish divergence)
              OR RSI(2) < 2 (extreme oversold).
              Entry confirmed when the next bar closes ABOVE the swing low bar's high.

SHORT (SELL): Price makes a new higher high while RSI(2) makes a lower high
              → RSI momentum is fading even as price rises (bearish divergence)
              OR RSI(2) > 94 (extreme overbought).
              Entry confirmed when the next bar closes BELOW the swing high bar's low.

Exit:
  - Opposite divergence signal detected while in a position
  - Or RSI crosses the opposite extreme threshold
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from src.data.base_provider import Bar
from src.strategies.base_strategy import BaseStrategy, Signal, SignalType


class RSIDivergenceStrategy(BaseStrategy):

    def __init__(
        self,
        rsi_period: int = 2,
        rsi_overbought: float = 94.0,
        rsi_oversold: float = 2.0,
        swing_lookback: int = 5,       # bars each side to confirm a local extreme
        max_divergence_bars: int = 60, # max bars between two swing points
        min_divergence_bars: int = 2,  # min bars between two swing points
        atr_period: int = 14,
    ):
        super().__init__(name="RSI Divergence")
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.swing_lookback = swing_lookback
        self.max_divergence_bars = max_divergence_bars
        self.min_divergence_bars = min_divergence_bars
        self.atr_period = atr_period
        self.reset()

    def reset(self):
        # Pre-conditions: divergence spotted, waiting for price confirmation
        self._pre_condition_buy = False
        self._pre_condition_short = False
        # The swing bar that triggered the pre-condition
        self._trigger_buy_bar: Optional[dict] = None   # swing low bar info
        self._trigger_short_bar: Optional[dict] = None  # swing high bar info
        # Track which swing indices we already used so we don't re-trigger
        self._last_buy_swing_idx: int = -1
        self._last_short_swing_idx: int = -1

    # ------------------------------------------------------------------
    # Indicators (all inline — no talib / pandas-ta)
    # ------------------------------------------------------------------

    def _rsi(self, close: pd.Series) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(
            alpha=1.0 / self.rsi_period, min_periods=self.rsi_period, adjust=False
        ).mean()
        avg_loss = loss.ewm(
            alpha=1.0 / self.rsi_period, min_periods=self.rsi_period, adjust=False
        ).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        return 100.0 - (100.0 / (1.0 + rs))

    def _atr(self, df: pd.DataFrame) -> pd.Series:
        h, l, pc = df["high"], df["low"], df["close"].shift(1)
        tr = pd.concat(
            [h - l, (h - pc).abs(), (l - pc).abs()], axis=1
        ).max(axis=1)
        return tr.ewm(
            alpha=1.0 / self.atr_period, min_periods=self.atr_period, adjust=False
        ).mean()

    # ------------------------------------------------------------------
    # Swing detection (backward-looking, confirmed with 1-bar delay)
    # ------------------------------------------------------------------

    def _find_swing_lows(self, low: pd.Series, rsi: pd.Series) -> list[dict]:
        """
        Return list of confirmed swing low dicts, oldest→newest.
        A bar at position i is a swing low if:
          - low[i] is the minimum of low[i-lb : i+1]
          - low[i+1] > low[i]  (price has started rising — 1-bar confirmation)
        We stop at len-2 so the last bar is never included (not yet confirmed).
        """
        lb = self.swing_lookback
        results = []
        for i in range(lb, len(low) - 1):
            if low.iloc[i] == low.iloc[i - lb : i + 1].min() and low.iloc[i + 1] > low.iloc[i]:
                results.append(
                    {
                        "idx": i,
                        "low": low.iloc[i],
                        "rsi": rsi.iloc[i],
                    }
                )
        return results

    def _find_swing_highs(self, high: pd.Series, rsi: pd.Series) -> list[dict]:
        """
        Return list of confirmed swing high dicts, oldest→newest.
        A bar at position i is a swing high if:
          - high[i] is the maximum of high[i-lb : i+1]
          - high[i+1] < high[i]  (price has started falling)
        """
        lb = self.swing_lookback
        results = []
        for i in range(lb, len(high) - 1):
            if high.iloc[i] == high.iloc[i - lb : i + 1].max() and high.iloc[i + 1] < high.iloc[i]:
                results.append(
                    {
                        "idx": i,
                        "high": high.iloc[i],
                        "rsi": rsi.iloc[i],
                    }
                )
        return results

    # ------------------------------------------------------------------
    # Main on_bar logic
    # ------------------------------------------------------------------

    def on_bar(
        self, bars_df: pd.DataFrame, current_bar: Bar, position: int
    ) -> Optional[Signal]:

        min_bars = max(self.rsi_period + 5, self.swing_lookback * 2 + 3)
        if len(bars_df) < min_bars:
            return None

        rsi = self._rsi(bars_df["close"])
        current_rsi = rsi.iloc[-1]
        current_close = bars_df["close"].iloc[-1]
        current_high = bars_df["high"].iloc[-1]
        current_low = bars_df["low"].iloc[-1]

        # ----------------------------------------------------------
        # 1. Check post-conditions (entry confirmation)
        # ----------------------------------------------------------

        # BUY post-condition: current bar closes ABOVE trigger swing low's high
        if self._pre_condition_buy and self._trigger_buy_bar is not None and position <= 0:
            trigger_high = self._trigger_buy_bar["bar_high"]
            if current_close > trigger_high:
                reason = (
                    f"Bullish RSI divergence confirmed — "
                    f"swing low RSI {self._trigger_buy_bar['rsi']:.1f} "
                    f"(prev low RSI {self._trigger_buy_bar['prev_rsi']:.1f}), "
                    f"price {self._trigger_buy_bar['low']:.2f} < "
                    f"prev low {self._trigger_buy_bar['prev_low']:.2f}"
                    + (" [EXTREME RSI<2]" if self._trigger_buy_bar.get("extreme") else "")
                )
                self._pre_condition_buy = False
                self._trigger_buy_bar = None
                return Signal(
                    signal_type=SignalType.BUY,
                    strategy_name=self.name,
                    timestamp=current_bar.timestamp,
                    price=current_close,
                    reason=reason,
                )

        # SHORT post-condition: current bar closes BELOW trigger swing high's low
        if self._pre_condition_short and self._trigger_short_bar is not None and position >= 0:
            trigger_low = self._trigger_short_bar["bar_low"]
            if current_close < trigger_low:
                reason = (
                    f"Bearish RSI divergence confirmed — "
                    f"swing high RSI {self._trigger_short_bar['rsi']:.1f} "
                    f"(prev high RSI {self._trigger_short_bar['prev_rsi']:.1f}), "
                    f"price {self._trigger_short_bar['high']:.2f} > "
                    f"prev high {self._trigger_short_bar['prev_high']:.2f}"
                    + (" [EXTREME RSI>94]" if self._trigger_short_bar.get("extreme") else "")
                )
                self._pre_condition_short = False
                self._trigger_short_bar = None
                return Signal(
                    signal_type=SignalType.SELL,
                    strategy_name=self.name,
                    timestamp=current_bar.timestamp,
                    price=current_close,
                    reason=reason,
                )

        # ----------------------------------------------------------
        # 2. Exit open positions on opposite extreme RSI
        # ----------------------------------------------------------
        if position > 0 and current_rsi > self.rsi_overbought:
            self._pre_condition_buy = False
            self._trigger_buy_bar = None
            return Signal(
                signal_type=SignalType.CLOSE,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_close,
                reason=f"RSI overbought exit ({current_rsi:.1f} > {self.rsi_overbought})",
            )

        if position < 0 and current_rsi < self.rsi_oversold:
            self._pre_condition_short = False
            self._trigger_short_bar = None
            return Signal(
                signal_type=SignalType.CLOSE,
                strategy_name=self.name,
                timestamp=current_bar.timestamp,
                price=current_close,
                reason=f"RSI oversold exit ({current_rsi:.1f} < {self.rsi_oversold})",
            )

        # ----------------------------------------------------------
        # 3. Detect new pre-conditions (divergence scanning)
        # ----------------------------------------------------------

        # --- BULLISH DIVERGENCE (BUY) ---
        if not self._pre_condition_buy:
            swing_lows = self._find_swing_lows(bars_df["low"], rsi)
            if len(swing_lows) >= 2:
                prev = swing_lows[-2]
                curr = swing_lows[-1]
                bars_apart = curr["idx"] - prev["idx"]

                if (
                    self.min_divergence_bars <= bars_apart <= self.max_divergence_bars
                    and curr["idx"] != self._last_buy_swing_idx
                ):
                    price_lower_low = curr["low"] < prev["low"]
                    rsi_higher_low = curr["rsi"] > prev["rsi"]
                    rsi_extreme = curr["rsi"] < self.rsi_oversold

                    if (price_lower_low and rsi_higher_low) or rsi_extreme:
                        self._pre_condition_buy = True
                        self._last_buy_swing_idx = curr["idx"]
                        self._trigger_buy_bar = {
                            "idx": curr["idx"],
                            "low": curr["low"],
                            "rsi": curr["rsi"],
                            "prev_low": prev["low"],
                            "prev_rsi": prev["rsi"],
                            # Price must break above this high to confirm entry
                            "bar_high": bars_df["high"].iloc[curr["idx"]],
                            "extreme": rsi_extreme,
                        }

        # --- BEARISH DIVERGENCE (SHORT) ---
        if not self._pre_condition_short:
            swing_highs = self._find_swing_highs(bars_df["high"], rsi)
            if len(swing_highs) >= 2:
                prev = swing_highs[-2]
                curr = swing_highs[-1]
                bars_apart = curr["idx"] - prev["idx"]

                if (
                    self.min_divergence_bars <= bars_apart <= self.max_divergence_bars
                    and curr["idx"] != self._last_short_swing_idx
                ):
                    price_higher_high = curr["high"] > prev["high"]
                    rsi_lower_high = curr["rsi"] < prev["rsi"]
                    rsi_extreme = curr["rsi"] > self.rsi_overbought

                    if (price_higher_high and rsi_lower_high) or rsi_extreme:
                        self._pre_condition_short = True
                        self._last_short_swing_idx = curr["idx"]
                        self._trigger_short_bar = {
                            "idx": curr["idx"],
                            "high": curr["high"],
                            "rsi": curr["rsi"],
                            "prev_high": prev["high"],
                            "prev_rsi": prev["rsi"],
                            # Price must break below this low to confirm entry
                            "bar_low": bars_df["low"].iloc[curr["idx"]],
                            "extreme": rsi_extreme,
                        }

        return None
