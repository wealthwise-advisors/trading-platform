"""
momentum.py
===========

RSI(13) divergence for IMP-06 -- the OQ-04 resolution.

>>> PROJECT DECISION, NOT SOURCE-DEFINED BEHAVIOUR <<<
The EWF reference names no indicator, no period, no comparison points and no
threshold. Its only statement is prose (WP-10, section 4.4): "prices reach a
new high but the indicators do not reach a new peak". The definition below was
supplied by project decision on 2026-08-09 because IMP-06 is mandatory and
therefore had to be made computable. It must never be cited as source-defined.

Definition (SRS FR-3.1a.2 .. FR-3.1a.8):

  Up-trending impulse   -- divergence iff wave 5's extreme is ABOVE wave 3's
                           extreme AND RSI(13) at wave 5's extreme is strictly
                           LOWER than RSI(13) at wave 3's extreme.
  Down-trending impulse -- divergence iff wave 5's extreme is BELOW wave 3's
                           extreme AND RSI(13) at wave 5's extreme is strictly
                           HIGHER than RSI(13) at wave 3's extreme.

Strictly directional. No tolerance band, no epsilon, no minimum divergence
magnitude, and no overbought/oversold levels (FR-3.1a.5). The platform's
RSI(13) chart bands are 70/30; they play no part here.

This module is the ONLY place in the package permitted to import shared
analysis code (ARCHITECTURE A-2 / FR-1f.3). Keeping that dependency in one
small file is what makes the independence guarantee greppable.
"""

from __future__ import annotations

import math

import pandas as pd

# The one permitted external dependency (FR-1.7 / FR-1f.3). calc_rsi is an
# indicator, not a pivot/swing detector, so it does not conflict with FR-1f.2.
from src.analysis.indicators import calc_rsi

from .models import Direction


def rsi_series(df: pd.DataFrame, period: int = 13) -> pd.Series:
    """RSI(period) over close, via the existing shared implementation.

    Note ``calc_rsi`` uses ``min_periods=period``, so the first ``period`` bars
    are NaN. That warmup is unavoidable and is exactly the case FR-3.1a.6
    routes to UNDECIDABLE rather than to a pass or a fail.
    """
    return calc_rsi(df["close"], period)


def _value_at(series: pd.Series, bar: int) -> float | None:
    if bar < 0 or bar >= len(series):
        return None
    v = float(series.iloc[bar])
    return None if math.isnan(v) else v


def has_divergence(
    rsi: pd.Series,
    wave3_index: int,
    wave3_price: float,
    wave5_index: int,
    wave5_price: float,
    direction: Direction,
) -> bool | None:
    """Evaluate IMP-06.

    Returns
    -------
    True   -- divergence present; IMP-06 satisfied.
    False  -- gate fails. Either wave 5 did not exceed wave 3 (the price
              precondition, FR-3.1a.8) or RSI did not diverge.
    None   -- UNDECIDABLE: RSI(13) unavailable at one of the two comparison
              bars (FR-3.1a.6). Never conflated with False.
    """
    r3 = _value_at(rsi, wave3_index)
    r5 = _value_at(rsi, wave5_index)
    if r3 is None or r5 is None:
        return None

    if direction is Direction.UP:
        if not (wave5_price > wave3_price):
            return False          # price precondition failed -> gate fails
        return r5 < r3
    else:
        if not (wave5_price < wave3_price):
            return False
        return r5 > r3
