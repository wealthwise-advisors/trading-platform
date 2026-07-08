"""
swing_identification.py
=======================

Swing (pivot) detection for price-action, Elliott-wave and divergence strategies.

Design goals
------------
1. Deterministic, non-repainting N-bar fractal pivots.
2. Confirmation-aware. A pivot at bar ``i`` is only *known* at bar ``i + right``,
   because you need the right-hand bars to close. The module therefore exposes
   BOTH the pivot index and the confirmation index. In a backtest you must only
   ever act on ``confirm_index`` -- using ``index`` is look-ahead bias and is the
   #1 way swing strategies look great on history and die live.
3. Optional minimum-move filter (absolute price, or derived from ATR) to drop
   noise pivots and enforce high/low alternation.
4. Market-structure labelling: HH / HL / LH / LL, plus a coarse trend read.

The detection layer (find_swings) is intentionally simple and auditable; the
filtering and labelling layers sit on top so you can swap any piece out.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #
class SwingType(str, Enum):
    HIGH = "high"
    LOW = "low"


class StructureLabel(str, Enum):
    HH = "HH"  # higher high
    LH = "LH"  # lower high
    HL = "HL"  # higher low
    LL = "LL"  # lower low


@dataclass
class Swing:
    """A single confirmed pivot."""
    index: int                          # bar where the pivot occurred
    confirm_index: int                  # bar where it became known (index + right)
    price: float                        # pivot price (bar high if HIGH, bar low if LOW)
    kind: SwingType
    label: Optional[StructureLabel] = None  # set by label_structure()


# --------------------------------------------------------------------------- #
# 1. Core detection: N-bar fractal
# --------------------------------------------------------------------------- #
def find_swings(high, low, left: int = 2, right: int = 2) -> List[Swing]:
    """Detect swing highs and lows with the N-bar fractal rule.

    A swing high at bar ``i`` requires ``high[i]`` to be strictly greater than the
    ``left`` highs before it and the ``right`` highs after it. Swing low is the
    mirror on ``low``. Strict comparison avoids double-counting flat tops/bottoms.

    Parameters
    ----------
    high, low : array-like of bar highs and lows.
    left, right : number of bars that must be lower (higher) on each side.
        ``right`` is the confirmation lag. Larger values -> fewer, more
        significant pivots, but later confirmation.

    Returns
    -------
    list[Swing] sorted by pivot index (highs and lows interleaved).
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must both be >= 1")

    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(high)
    swings: List[Swing] = []

    for i in range(left, n - right):
        h = high[i]
        if h > high[i - left:i].max() and h > high[i + 1:i + 1 + right].max():
            swings.append(Swing(i, i + right, float(h), SwingType.HIGH))

        l = low[i]
        if l < low[i - left:i].min() and l < low[i + 1:i + 1 + right].min():
            swings.append(Swing(i, i + right, float(l), SwingType.LOW))

    swings.sort(key=lambda s: s.index)
    return swings


# --------------------------------------------------------------------------- #
# 2. Noise filter: alternation + minimum amplitude
# --------------------------------------------------------------------------- #
def filter_swings(swings: List[Swing], min_move: float = 0.0) -> List[Swing]:
    """Enforce high/low alternation and drop tiny counter-swings.

    - Consecutive same-type pivots collapse to the more extreme one
      (e.g. two swing highs in a row -> keep the higher).
    - An opposite pivot is ignored if it reverses less than ``min_move``
      (absolute price) from the last kept pivot.

    ``min_move`` of 0 keeps everything except the alternation collapse.
    A single forward pass; good enough in practice, not provably optimal.
    """
    if not swings:
        return []

    kept: List[Swing] = [swings[0]]
    for s in swings[1:]:
        last = kept[-1]
        if s.kind == last.kind:
            more_extreme = (s.kind == SwingType.HIGH and s.price > last.price) or \
                           (s.kind == SwingType.LOW and s.price < last.price)
            if more_extreme:
                kept[-1] = s
        else:
            if abs(s.price - last.price) >= min_move:
                kept.append(s)
            # else: counter-swing too small, skip it
    return kept


# --------------------------------------------------------------------------- #
# 3. Structure labelling: HH / HL / LH / LL
# --------------------------------------------------------------------------- #
def label_structure(swings: List[Swing]) -> List[Swing]:
    """Label each pivot relative to the previous pivot of the SAME type.

    Swing highs become HH or LH; swing lows become HL or LL. The first pivot of
    each type has no predecessor, so its label stays None. Mutates and returns
    the list.
    """
    last_high: Optional[float] = None
    last_low: Optional[float] = None

    for s in swings:
        if s.kind == SwingType.HIGH:
            if last_high is not None:
                s.label = StructureLabel.HH if s.price > last_high else StructureLabel.LH
            last_high = s.price
        else:
            if last_low is not None:
                s.label = StructureLabel.HL if s.price > last_low else StructureLabel.LL
            last_low = s.price
    return swings


def trend_state(swings: List[Swing]) -> str:
    """Coarse trend read from the most recent labelled high and low.

    uptrend   = last high is HH and last low is HL
    downtrend = last high is LH and last low is LL
    otherwise = range / transition
    """
    last_high_label = next(
        (s.label for s in reversed(swings)
         if s.kind == SwingType.HIGH and s.label is not None), None)
    last_low_label = next(
        (s.label for s in reversed(swings)
         if s.kind == SwingType.LOW and s.label is not None), None)

    if last_high_label == StructureLabel.HH and last_low_label == StructureLabel.HL:
        return "uptrend"
    if last_high_label == StructureLabel.LH and last_low_label == StructureLabel.LL:
        return "downtrend"
    return "range / transition"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def atr(high, low, close, period: int = 14) -> np.ndarray:
    """Average True Range (Wilder smoothing). Handy for an adaptive min_move."""
    high = np.asarray(high, float)
    low = np.asarray(low, float)
    close = np.asarray(close, float)
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum.reduce([high - low,
                            np.abs(high - prev_close),
                            np.abs(low - prev_close)])
    out = np.full_like(tr, np.nan)
    if len(tr) >= period:
        out[period - 1] = tr[:period].mean()
        for i in range(period, len(tr)):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def swings_to_frame(swings: List[Swing]) -> pd.DataFrame:
    """Tidy DataFrame view of the detected swings."""
    return pd.DataFrame([{
        "index": s.index,
        "confirm_index": s.confirm_index,
        "kind": s.kind.value,
        "price": round(s.price, 4),
        "label": s.label.value if s.label else None,
    } for s in swings])


# --------------------------------------------------------------------------- #
# One-call pipeline
# --------------------------------------------------------------------------- #
def identify_swings(df: pd.DataFrame, left: int = 2, right: int = 2,
                    min_move: float = 0.0) -> List[Swing]:
    """detect -> filter -> label. Expects columns 'high' and 'low'."""
    swings = find_swings(df["high"], df["low"], left, right)
    swings = filter_swings(swings, min_move)
    swings = label_structure(swings)
    return swings


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    rng = np.random.default_rng(7)
    n = 300
    drift = rng.normal(0, 1, n).cumsum()
    close = 100 + drift + np.sin(np.linspace(0, 12, n)) * 5      # trend + waves
    high = close + rng.uniform(0.2, 1.0, n)
    low = close - rng.uniform(0.2, 1.0, n)
    df = pd.DataFrame({"high": high, "low": low, "close": close})

    a = atr(df["high"], df["low"], df["close"], 14)
    min_move = 1.0 * float(np.nanmedian(a))        # require ~1 ATR reversal

    swings = identify_swings(df, left=2, right=2, min_move=min_move)
    frame = swings_to_frame(swings)

    print(f"bars={n}  pivots found={len(swings)}  min_move={min_move:.2f}")
    print("\nlast 12 confirmed swings:")
    print(frame.tail(12).to_string(index=False))
    print("\ncurrent structure:", trend_state(swings))
    print("confirmation lag = right = 2 bars  ->  act on confirm_index, never index")
