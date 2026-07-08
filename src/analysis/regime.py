"""
regime.py
=========

Classify the current market regime from trailing OHLC bars: trending (up or
down), sideways/choppy, or high-volatility. Pure statistics -- no LLM, no
external API, runs entirely locally.

Two numbers drive the classification:
  - trend_strength : (EMA fast - EMA slow) / ATR  -- how far apart the moving
    averages are, scaled by the instrument's own recent volatility so it's
    comparable across symbols/timeframes.
  - vol_ratio       : current ATR / its own trailing median -- how volatile
    right now is versus "normal" for this instrument recently.

Honesty: this is a heuristic snapshot of recent price action, not a forecast.
Regimes can flip quickly; a strategy built on this should expect occasional
whipsaws right at regime boundaries.
"""

from __future__ import annotations

import pandas as pd


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def classify_regime(
    df: pd.DataFrame,
    fast: int = 9,
    slow: int = 21,
    atr_period: int = 14,
    vol_window: int = 50,
    trend_threshold: float = 0.6,
    vol_high_threshold: float = 1.4,
) -> dict:
    """
    Classify the regime as of the LAST row of ``df`` (expects 'high','low','close').

    Returns a dict: {"regime": one of "trending_up"/"trending_down"/
    "sideways"/"high_volatility"/"insufficient_data", "trend_strength": float,
    "vol_ratio": float}.
    """
    needed = max(slow, atr_period, vol_window) + 1
    if len(df) < needed:
        return {"regime": "insufficient_data", "trend_strength": 0.0, "vol_ratio": 1.0}

    close, high, low = df["close"], df["high"], df["low"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    atr = _atr(high, low, close, atr_period)

    last_atr = float(atr.iloc[-1])
    if not last_atr or pd.isna(last_atr):
        return {"regime": "insufficient_data", "trend_strength": 0.0, "vol_ratio": 1.0}

    atr_baseline = float(atr.iloc[-vol_window:].median())
    vol_ratio = last_atr / atr_baseline if atr_baseline else 1.0
    trend_strength = (ema_fast.iloc[-1] - ema_slow.iloc[-1]) / last_atr

    if vol_ratio >= vol_high_threshold:
        regime = "high_volatility"
    elif trend_strength >= trend_threshold:
        regime = "trending_up"
    elif trend_strength <= -trend_threshold:
        regime = "trending_down"
    else:
        regime = "sideways"

    return {
        "regime": regime,
        "trend_strength": round(float(trend_strength), 3),
        "vol_ratio": round(float(vol_ratio), 3),
    }
