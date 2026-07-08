"""
corrective_waves.py
===================

Rule-based classification of Elliott CORRECTIVE structures, built on the
confirmed swing pivots from ``swing_identification``.

Taxonomy encoded
----------------
Simple corrections (single structures):
  ZIGZAG        5-3-5  sharp;   B retraces A shallowly (< ~90%)
  REGULAR_FLAT  3-3-5  sideways; B ~ back to start of A (~90-105%)
  EXPANDED_FLAT 3-3-5  B overshoots the start of A; C overshoots end of A
  RUNNING_FLAT  3-3-5  B overshoots start; C falls short of end of A
  TRIANGLE      3-3-3-3-3  five converging (or expanding) legs

Complex corrections (COMBINATIONS joined by X-wave connectors):
  DOUBLE_THREE  W - X - Y          (two simple corrections + one connector)
  TRIPLE_THREE  W - X - Y - X - Z  (three simple corrections + two connectors)

Honesty / limits (read this)
----------------------------
* Corrections are the most subjective part of Elliott and combinations are the
  most subjective corrections -- they are frequently a "catch-all" fitted in
  hindsight. Everything here returns a CANDIDATE with its ratios exposed so you
  can audit it, never a verdict.
* Precise 5-3-5 vs 3-3-5 subdivision needs sub-wave analysis. ``count_subwaves``
  approximates it by re-detecting pivots at higher sensitivity on one leg; it is
  a heuristic, noisy on a single timeframe. For real work, verify subdivisions
  on a lower timeframe and track ALTERNATE counts rather than one answer.
* Thresholds below are conventional defaults; tune them per instrument.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd

from .swing_identification import Swing, SwingType, find_swings, identify_swings


class CorrectionType(str, Enum):
    ZIGZAG = "zigzag"
    REGULAR_FLAT = "regular_flat"
    EXPANDED_FLAT = "expanded_flat"
    RUNNING_FLAT = "running_flat"
    TRIANGLE = "triangle"
    DOUBLE_THREE = "double_three"
    TRIPLE_THREE = "triple_three"
    UNKNOWN = "unknown"


@dataclass
class Correction:
    type: CorrectionType
    direction: str                     # 'up' / 'down' net move
    pivots: List[Swing]
    metrics: dict
    subparts: Optional[list] = None    # combinations: [Correction, 'X', Correction, ...]

    @property
    def start_index(self) -> int:
        return self.pivots[0].index

    @property
    def end_index(self) -> int:
        return self.pivots[-1].index


_SIMPLE = {CorrectionType.ZIGZAG, CorrectionType.REGULAR_FLAT,
           CorrectionType.EXPANDED_FLAT, CorrectionType.RUNNING_FLAT}


# --------------------------------------------------------------------------- #
# Simple ABC classification (zigzag vs flat variants)
# --------------------------------------------------------------------------- #
def classify_abc(pivots: List[Swing],
                 zigzag_max: float = 0.90,
                 flat_max: float = 1.05,
                 c_short_eps: float = 0.05) -> Correction:
    """Classify a 4-pivot corrective segment (Start, A, B, C).

    b_retrace_of_A : how far B retraces wave A (1.0 == B back at the start).
    c_beyond_A     : how far C extends past the end of A (fraction of A; >0 = new extreme).
    """
    if len(pivots) != 4:
        raise ValueError("classify_abc needs exactly 4 pivots: Start, A, B, C")

    S, A, B, C = (p.price for p in pivots)
    down = pivots[0].kind == SwingType.HIGH          # correction net down starts at a high

    if down:
        leg_a = S - A
        b_retrace = (B - A) / leg_a if leg_a else 0.0
        c_beyond = (A - C) / leg_a if leg_a else 0.0
    else:
        leg_a = A - S
        b_retrace = (A - B) / leg_a if leg_a else 0.0
        c_beyond = (C - A) / leg_a if leg_a else 0.0

    metrics = {"b_retrace_of_A": round(b_retrace, 3),
               "c_beyond_A": round(c_beyond, 3)}

    if b_retrace < zigzag_max:
        ctype = CorrectionType.ZIGZAG
    elif b_retrace > flat_max:
        ctype = (CorrectionType.EXPANDED_FLAT if c_beyond > c_short_eps
                 else CorrectionType.RUNNING_FLAT)
    else:
        ctype = CorrectionType.REGULAR_FLAT

    return Correction(ctype, "down" if down else "up", list(pivots), metrics)


# --------------------------------------------------------------------------- #
# Triangle detection (5 converging/expanding legs)
# --------------------------------------------------------------------------- #
def detect_triangle(pivots: List[Swing]) -> Optional[Correction]:
    """Detect a simple triangle from 6 alternating pivots (start + A..E)."""
    if len(pivots) < 6:
        return None
    highs = [p.price for p in pivots if p.kind == SwingType.HIGH]
    lows = [p.price for p in pivots if p.kind == SwingType.LOW]
    if len(highs) < 3 or len(lows) < 3:
        return None

    desc = lambda xs: all(xs[i] > xs[i + 1] for i in range(len(xs) - 1))
    asc = lambda xs: all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))

    if desc(highs) and asc(lows):
        shape = "contracting"
    elif asc(highs) and desc(lows):
        shape = "expanding"
    else:
        return None

    direction = "down" if pivots[0].kind == SwingType.HIGH else "up"
    metrics = {"shape": shape,
               "high_convergence": round(highs[0] - highs[-1], 3),
               "low_convergence": round(lows[-1] - lows[0], 3)}
    return Correction(CorrectionType.TRIANGLE, direction, pivots[:6], metrics)


# --------------------------------------------------------------------------- #
# Heuristic sub-wave counter: impulsive (5) vs corrective (3)
# --------------------------------------------------------------------------- #
def count_subwaves(df: pd.DataFrame, i0: int, i1: int, sensitivity: int = 1) -> dict:
    """Re-detect pivots at higher sensitivity within bars [i0, i1] to estimate
    whether a leg subdivides into ~5 (impulsive) or ~3 (corrective).

    HEURISTIC: sub-pivot counts are noisy on one timeframe. Use as a hint only.
    """
    seg = df.iloc[i0:i1 + 1]
    if len(seg) < 2 * sensitivity + 2:
        return {"sub_pivots": 0, "guess": "unknown"}
    subs = find_swings(seg["high"], seg["low"], left=sensitivity, right=sensitivity)
    n = len(subs)
    guess = "impulsive(~5)" if n >= 4 else "corrective(~3)" if n >= 2 else "unknown"
    return {"sub_pivots": n, "guess": guess}


# --------------------------------------------------------------------------- #
# Complex combinations: double / triple three
# --------------------------------------------------------------------------- #
def _range(pivots: List[Swing]) -> float:
    ps = [p.price for p in pivots]
    return max(ps) - min(ps)


def find_combinations(swings: List[Swing],
                      x_min: float = 0.30, x_max: float = 1.40) -> List[Correction]:
    """Detect double- and triple-three combinations by chaining simple
    corrections through X-wave connectors.

    A candidate double three spans 8 pivots: W = [i..i+3] (Start,A,B,C),
    the X connector is the leg C_W -> pivot[i+4], and Y = [i+4..i+7]. A triple
    three extends with another X and Z = [i+8..i+11].

    The X connector must retrace between ``x_min`` and ``x_max`` of W's range,
    keeping the whole structure sideways/corrective. Heuristic -- see module docstring.
    """
    out: List[Correction] = []
    n = len(swings)

    for i in range(n - 7):
        w = classify_abc(swings[i:i + 4])
        if w.type not in _SIMPLE:
            continue
        c_w = swings[i + 3]            # end of W
        x_end = swings[i + 4]          # end of the X connector
        x_move = abs(x_end.price - c_w.price)
        w_rng = _range(swings[i:i + 4]) or 1e-9
        if not (x_min <= x_move / w_rng <= x_max):
            continue

        y = classify_abc(swings[i + 4:i + 8])
        if y.type not in _SIMPLE:
            continue

        subparts = [w, "X", y]
        ctype = CorrectionType.DOUBLE_THREE
        end = i + 7

        # try to extend to a triple three
        if i + 11 < n:
            c_y = swings[i + 7]
            x2_end = swings[i + 8]
            x2_move = abs(x2_end.price - c_y.price)
            y_rng = _range(swings[i + 4:i + 8]) or 1e-9
            if x_min <= x2_move / y_rng <= x_max:
                z = classify_abc(swings[i + 8:i + 12])
                if z.type in _SIMPLE:
                    subparts = [w, "X", y, "X", z]
                    ctype = CorrectionType.TRIPLE_THREE
                    end = i + 11

        direction = "down" if swings[i].kind == SwingType.HIGH else "up"
        metrics = {"W": w.type.value, "Y": y.type.value,
                   "x_retrace_of_W": round(x_move / w_rng, 3)}
        if ctype == CorrectionType.TRIPLE_THREE:
            metrics["Z"] = subparts[4].type.value
        out.append(Correction(ctype, direction, swings[i:end + 1], metrics, subparts))

    return out


# --------------------------------------------------------------------------- #
# Pretty print
# --------------------------------------------------------------------------- #
def describe(c: Correction) -> str:
    base = (f"{c.type.value:<13} [{c.direction}] "
            f"bars {c.start_index}->{c.end_index}  {c.metrics}")
    if c.subparts:
        pieces = " ".join(p if isinstance(p, str) else p.type.value for p in c.subparts)
        base += f"  = ({pieces})"
    return base


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _mk(idx: int, price: float, kind: SwingType) -> Swing:
    return Swing(idx, idx + 2, price, kind)


if __name__ == "__main__":
    H, L = SwingType.HIGH, SwingType.LOW

    print("=== simple ABC classification (Start, A, B, C) ===")
    cases = {
        "sharp down":     [_mk(0, 120, H), _mk(3, 100, L), _mk(6, 115, H), _mk(9, 92, L)],
        "regular flat":   [_mk(0, 120, H), _mk(3, 104, L), _mk(6, 119, H), _mk(9, 102, L)],
        "expanded flat":  [_mk(0, 120, H), _mk(3, 104, L), _mk(6, 124, H), _mk(9, 100, L)],
        "running flat":   [_mk(0, 120, H), _mk(3, 104, L), _mk(6, 124, H), _mk(9, 106, L)],
    }
    for name, piv in cases.items():
        print(f"  {name:<14} -> {describe(classify_abc(piv))}")

    print("\n=== triangle detection (Start + A..E) ===")
    tri = [_mk(0, 120, H), _mk(3, 100, L), _mk(6, 116, H),
           _mk(9, 104, L), _mk(12, 112, H), _mk(15, 107, L)]
    print("  " + describe(detect_triangle(tri)))

    print("\n=== complex combination (double three: W=expanded flat, X, Y=zigzag) ===")
    combo = [_mk(0, 120, H), _mk(3, 104, L), _mk(6, 124, H), _mk(9, 100, L),   # W
             _mk(12, 114, H),                                                   # X end
             _mk(15, 98, L), _mk(18, 108, H), _mk(21, 90, L)]                   # Y
    for c in find_combinations(combo):
        print("  " + describe(c))

    print("\n=== heuristic sub-wave count on a leg ===")
    # a 5-wave-ish leg vs a 3-wave-ish leg, built as tiny price paths
    rng = np.random.default_rng(0)
    impulse_leg = np.array([10, 12, 11, 15, 14, 18])            # up with pullbacks (~impulsive)
    corr_leg = np.array([10, 13, 11.5, 12.5])                   # simpler (~corrective)

    def leg_df(prices):
        return pd.DataFrame({"high": prices + 0.2, "low": prices - 0.2, "close": prices})

    print("  impulse-like leg:", count_subwaves(leg_df(impulse_leg), 0, len(impulse_leg) - 1))
    print("  corrective leg:  ", count_subwaves(leg_df(corr_leg), 0, len(corr_leg) - 1))

    print("\nNOTE: candidates with ratios exposed -- audit them; verify subdivisions"
          " on a lower timeframe and track alternate counts.")
