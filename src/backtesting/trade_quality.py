"""
trade_quality.py
================

Post-hoc "setup quality" score (0-100) for each executed trade, based on
entry-time context -- NOT on the trade's P&L outcome. The point is to
separate "was this a good setup" from "did it work", so a good setup that
lost money and a lucky bad setup that won both get scored honestly.

Components (each 0-10, averaged and scaled to 0-100):
  - trend_strength : (EMA9-EMA21)/ATR at entry, signed favorably for the
    trade's direction (trading WITH the trend scores higher).
  - momentum        : RSI(2) positioned favorably for the trade's direction
    (long favored coming off oversold, short favored coming off overbought).
  - volume          : entry-bar volume vs its trailing 20-bar average
    (skipped, and remaining components re-weighted, if no volume column).
  - support_zone    : how close entry price is to a recent swing low (long)
    or swing high (short) -- trading near a level scores higher than trading
    in the middle of nowhere.

Honesty: this scores the SETUP, not the outcome. A high score does not mean
the trade won; a low score does not mean it lost. Use it to spot patterns in
what kinds of setups this strategy tends to take, not as a stop-loss trigger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from src.backtesting.results import BacktestResults
from src.analysis.swing_identification import identify_swings, SwingType


@dataclass
class TradeQuality:
    trade_index: int
    score: float                # 0-100
    components: dict            # name -> 0-10
    grade: str                  # "Excellent" / "Good" / "Fair" / "Poor"


def _grade(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Poor"


def _calc_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low, (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def score_trades(results: BacktestResults, swing_lookback_bars: int = 30) -> List[TradeQuality]:
    """Score every trade in ``results.trades`` on its entry-time setup quality."""
    df = results.price_data
    if df.empty or not results.trades:
        return []

    close, high, low = df["close"], df["high"], df["low"]
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    atr14 = _atr(high, low, close, 14)
    rsi2 = _calc_rsi(close, 2)
    has_volume = "volume" in df.columns and df["volume"].notna().any()
    vol_avg20 = df["volume"].rolling(20).mean() if has_volume else None

    swings = identify_swings(df.reset_index(drop=True), left=2, right=2, min_move=0.0)
    swing_highs = [s for s in swings if s.kind == SwingType.HIGH]
    swing_lows = [s for s in swings if s.kind == SwingType.LOW]

    idx_lookup = {ts: i for i, ts in enumerate(df.index)}

    out: List[TradeQuality] = []
    for ti, t in enumerate(results.trades):
        pos = idx_lookup.get(t.entry_time)
        if pos is None or pos >= len(df):
            continue

        components: dict = {}

        atr_val = atr14.iloc[pos]
        has_atr = pd.notna(atr_val) and atr_val != 0
        trend_gap = (ema9.iloc[pos] - ema21.iloc[pos]) / atr_val if has_atr else 0.0
        signed_trend = trend_gap if t.direction == "LONG" else -trend_gap
        components["trend_strength"] = round(float(np.clip(5 + signed_trend * 5, 0, 10)), 1)

        r = rsi2.iloc[pos]
        if pd.isna(r):
            momentum = 5.0
        elif t.direction == "LONG":
            momentum = np.clip((50 - r) / 50 * 10, 0, 10)   # oversold -> higher score
        else:
            momentum = np.clip((r - 50) / 50 * 10, 0, 10)   # overbought -> higher score
        components["momentum"] = round(float(momentum), 1)

        if has_volume:
            avg_v = vol_avg20.iloc[pos]
            v = df["volume"].iloc[pos]
            vol_ratio = (v / avg_v) if (pd.notna(avg_v) and avg_v != 0 and pd.notna(v)) else 1.0
            components["volume"] = round(float(np.clip(vol_ratio * 5, 0, 10)), 1)

        lookback_start = max(0, pos - swing_lookback_bars)
        relevant = swing_lows if t.direction == "LONG" else swing_highs
        nearby = [s for s in relevant if lookback_start <= s.index < pos]
        if nearby and has_atr:
            nearest = min(nearby, key=lambda s: abs(s.price - t.entry_price))
            dist_atr = abs(nearest.price - t.entry_price) / atr_val
            components["support_zone"] = round(float(np.clip(10 - dist_atr * 3, 0, 10)), 1)
        else:
            components["support_zone"] = 5.0

        avg_score = sum(components.values()) / len(components)
        score = round(avg_score * 10, 1)
        out.append(TradeQuality(trade_index=ti, score=score, components=components, grade=_grade(score)))

    return out
