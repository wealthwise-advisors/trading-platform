"""
indicators.py
=============

RSI and Stochastic calculations, extracted verbatim from
ui/components/charts.py so the FastAPI backend and the Streamlit app share one
implementation instead of forking it. No logic changes from the originals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calc_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))


def calc_stoch(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, smooth_k: int = 3, d_period: int = 3):
    lowest = low.rolling(k_period).min()
    highest = high.rolling(k_period).max()
    rng = (highest - lowest).replace(0, np.nan)
    raw_k = 100.0 * (close - lowest) / rng
    k = raw_k.rolling(smooth_k).mean()   # Slow %K
    d = k.rolling(d_period).mean()        # Slow %D
    return k, d
