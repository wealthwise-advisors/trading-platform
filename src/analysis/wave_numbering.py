"""
wave_numbering.py
==================

Continuous, sequential Elliott Wave numbering across a full swing series.

Philosophy
----------
``elliott_wave.py``'s ``find_impulses()`` answers "is THIS specific 6-pivot
window a legal impulse?" -- a strict, single-window validator. This module
answers a different question: "walking left-to-right through the whole
chart, what continuous wave count would a chart annotate?" -- producing
Wave 1, 2, 3, 4, 5, continuation waves 6..11 (if the move keeps extending),
and a closing a/b/c correction, the way a real Elliott Wave chart service
labels every swing.

This is a from-scratch reimplementation of the numbering approach used by
the wealthwise-advisors/Wealthwise reference repo's ``assign_wave_numbers()``
(``py_scripts/assign_wave_numbers.py``) -- ported to our ``Swing``/
``identify_swings`` pivot model instead of raw pandas-ta zigzag columns,
with corrected defects found in the original:

  1. Wave 4's retracement gate had two different values across branches
     (78.2% in one, 78.6% everywhere else) -- unified to 78.6% here.
  2. The reference re-attempts a fresh count from EVERY pivot and lets later
     attempts silently overwrite earlier ones on overlap (an emergent
     "last writer wins" effect, not a designed one), which makes labels
     unstable across recomputes. This module does one deterministic
     left-to-right pass instead: once a swing is consumed by a kept count,
     it is never reconsidered.
  3. The ``.1``/``.2`` confidence suffix (both Fibonacci+pattern conditions
     met vs. pattern-only) is computed in the reference but never actually
     used downstream (chart color is identical either way). Here it's a
     real field (``WaveLabel.sub``) meant to drive visual confidence (e.g. a
     dimmer marker for ``.2``).

Fibonacci gates (as tuned/validated in the reference, not textbook defaults)
-----------------------------------------------------------------------------
  Wave 2 retraces   38.2% -  85.1% of Wave 1
  Wave 3 extends   161.8% - 261.8% of Wave 1
  Wave 4 retraces    14.6% -  78.6% of Wave 1 (unified; see defect #1 above)
  Wave 5 extends   123.6% - 161.8% of Wave 4

Scope
-----
Impulse waves 1-5 (+ continuation 6-11) and a closing simple a/b/c only.
Complex corrective structures (flats, triangles, double/triple three) are
NOT covered here -- see ``corrective_waves.py`` for a separate, simpler
classifier of the correction that follows an impulse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal, Optional

from .swing_identification import Swing, SwingType, identify_swings

Direction = Literal["up", "down"]

# --------------------------------------------------------------------------- #
# Fibonacci gates
# --------------------------------------------------------------------------- #
WAVE2_RETRACE = (0.382, 0.851)      # of wave 1
WAVE3_EXTENSION = (1.618, 2.618)    # of wave 1, added past wave 1's end
WAVE4_RETRACE = (0.146, 0.786)      # of wave 1, retraced back from wave 3's end
WAVE5_EXTENSION = (1.236, 1.618)    # of wave 4's length, added past wave 4's end

MAX_CONTINUATION = 11               # cap on continuation waves (mirrors the reference's own cap)


@dataclass
class WaveLabel:
    swing: Swing
    wave: str                       # "1".."11" or "a"/"b"/"c"
    sub: Optional[int]              # 1 (fib+pattern both met) / 2 (pattern only) / None (n/a)
    direction: Direction

    @property
    def index(self) -> int:
        return self.swing.index

    @property
    def price(self) -> float:
        return self.swing.price

    @property
    def label(self) -> str:
        return f"{self.wave}.{self.sub}" if self.sub else self.wave


def _in_range(x: float, lo: float, hi: float) -> bool:
    return lo <= x <= hi


def _first_hit(swings: List[Swing], first_idx: int,
               predicate: Callable[[Swing], bool]) -> Optional[int]:
    """Try swings[first_idx]; on failure, retry at swings[first_idx + 2]
    (skip one opposite-kind pivot, landing on the next same-kind extreme --
    mirrors the reference's ``i += 2`` "try the next same-direction pivot"
    fallback). Returns the accepted index, or None if both fail / run out.
    """
    for j in (first_idx, first_idx + 2):
        if j >= len(swings):
            return None
        if predicate(swings[j]):
            return j
    return None


# --------------------------------------------------------------------------- #
# Grow one candidate count forward from a Wave-1 seed
# --------------------------------------------------------------------------- #
def _grow_count(swings: List[Swing], start: int) -> Optional[tuple[List[WaveLabel], int]]:
    """Try to build a wave count with Wave 1 = swings[start] (swings[start-1]
    is its origin). Returns (labels, next_unconsumed_index) if it reaches at
    least Wave 3, else None.
    """
    if start < 1 or start >= len(swings):
        return None

    origin = swings[start - 1]
    w1 = swings[start]
    direction: Direction = "up" if w1.kind == SwingType.HIGH else "down"
    sign = 1.0 if direction == "up" else -1.0

    len1 = sign * (w1.price - origin.price)
    if len1 <= 0:
        return None

    labels: List[WaveLabel] = [WaveLabel(w1, "1", None, direction)]

    # ---- Wave 2: gated retracement of Wave 1. No retry -- an immediate
    # failure invalidates this whole candidate (mirrors the reference, the
    # one transition with no skip-ahead fallback). ----
    if start + 1 >= len(swings):
        return None
    w2 = swings[start + 1]
    retrace2 = sign * (w1.price - w2.price) / len1
    if not (0.0 < retrace2 <= 1.0):    # stays within (origin, wave1] -- w2_holds_origin
        return None
    sub2 = 1 if _in_range(retrace2, *WAVE2_RETRACE) else 2
    labels.append(WaveLabel(w2, "2", sub2, direction))
    cursor = start + 1

    # ---- Wave 3: gated extension of Wave 1, one skip-ahead retry ----
    def _w3_ok(c: Swing) -> bool:
        return c.kind == w1.kind and sign * (c.price - w1.price) > 0  # w3_exceeds_w1

    idx3 = _first_hit(swings, cursor + 1, _w3_ok)
    if idx3 is None:
        return None  # wave 3 never established -- discard the whole attempt
    w3 = swings[idx3]
    ext3 = sign * (w3.price - w1.price) / len1
    sub3 = 1 if _in_range(ext3, *WAVE3_EXTENSION) else 2
    labels.append(WaveLabel(w3, "3", sub3, direction))
    cursor = idx3

    # ---- Wave 4: gated retracement of Wave 1 (measured off Wave 3), one
    # skip-ahead retry. Failure here still keeps the 1-2-3 partial count. ----
    def _w4_ok(c: Swing) -> bool:
        return (c.kind == origin.kind
                and sign * (c.price - w1.price) > 0    # w4_no_overlap_w1
                and sign * (w3.price - c.price) > 0)   # genuine pullback off wave 3

    idx4 = _first_hit(swings, cursor + 1, _w4_ok)
    if idx4 is None:
        return labels, cursor + 1
    w4 = swings[idx4]
    retrace4 = sign * (w3.price - w4.price) / len1
    sub4 = 1 if _in_range(retrace4, *WAVE4_RETRACE) else 2
    labels.append(WaveLabel(w4, "4", sub4, direction))
    cursor = idx4

    # ---- Wave 5: gated extension of Wave 4, one skip-ahead retry. Failure
    # here still keeps the 1-2-3-4 partial count. ----
    len4 = sign * (w3.price - w4.price)

    def _w5_ok(c: Swing) -> bool:
        return c.kind == w1.kind and sign * (c.price - w4.price) > 0

    idx5 = _first_hit(swings, cursor + 1, _w5_ok)
    if idx5 is None:
        return labels, cursor + 1
    w5 = swings[idx5]
    ext5 = sign * (w5.price - w4.price) / len4
    sub5 = 1 if _in_range(ext5, *WAVE5_EXTENSION) else 2
    labels.append(WaveLabel(w5, "5", sub5, direction))
    cursor = idx5

    # ---- Continuation (6..11), or a closing a/b/c ----
    cursor = _extend_or_close(swings, cursor, sign, direction, labels)

    return labels, cursor + 1


def _extend_or_close(swings: List[Swing], cursor: int, sign: float, direction: Direction,
                     labels: List[WaveLabel]) -> int:
    """After Wave 5 (swings[cursor]), keep numbering 6..MAX_CONTINUATION while
    price keeps making new extremes in the trend direction; once that stops,
    label one more alternating triple as a closing a/b/c if it shows a clean
    reversal. Returns the new cursor (index of the last consumed swing).
    """
    n = len(swings)
    trend_kind = swings[cursor].kind
    last_trend_price = swings[cursor].price
    wave_num = 6

    while wave_num <= MAX_CONTINUATION and cursor + 2 < n:
        pullback, extreme = swings[cursor + 1], swings[cursor + 2]
        if extreme.kind != trend_kind or sign * (extreme.price - last_trend_price) <= 0:
            break
        labels.append(WaveLabel(pullback, str(wave_num), None, direction))
        wave_num += 1
        labels.append(WaveLabel(extreme, str(wave_num), None, direction))
        wave_num += 1
        last_trend_price = extreme.price
        cursor += 2

    if cursor + 3 < n:
        a, b, c = swings[cursor + 1], swings[cursor + 2], swings[cursor + 3]
        reversal = (a.kind != trend_kind and sign * (last_trend_price - a.price) > 0
                    and b.kind == trend_kind and c.kind != trend_kind
                    and sign * (c.price - a.price) < 0)
        if reversal:
            labels.append(WaveLabel(a, "a", None, direction))
            labels.append(WaveLabel(b, "b", None, direction))
            labels.append(WaveLabel(c, "c", None, direction))
            cursor += 3

    return cursor


# --------------------------------------------------------------------------- #
# Driver: one deterministic left-to-right pass over the whole series
# --------------------------------------------------------------------------- #
def label_wave_sequence(swings: List[Swing]) -> List[WaveLabel]:
    """Walk the whole swing series left-to-right, labeling continuous Elliott
    wave counts as they're found. Once a swing is consumed by a kept count it
    is never reconsidered -- deliberately different from the reference's
    per-pivot overwrite-composite (see module docstring, defect #2).
    """
    out: List[WaveLabel] = []
    i = 1
    n = len(swings)
    while i < n:
        result = _grow_count(swings, i)
        if result is None:
            i += 1
            continue
        labels, next_i = result
        out.extend(labels)
        i = max(next_i, i + 1)
    return out


# --------------------------------------------------------------------------- #
# Pretty print
# --------------------------------------------------------------------------- #
def describe_sequence(labels: List[WaveLabel]) -> str:
    return "\n".join(
        f"  bar {w.index:>3}  {w.direction:<4}  Wave {w.label:<5}  @ {w.price:.2f}"
        for w in labels
    )


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.2, seed=1):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    closes = []
    for a, b in zip(pivots, pivots[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivots[-1])
    closes = np.asarray(closes) + rng.normal(0, noise, len(closes))
    high = closes + rng.uniform(0.1, 0.5, len(closes))
    low = closes - rng.uniform(0.1, 0.5, len(closes))
    return pd.DataFrame({"high": high, "low": low, "close": closes})


if __name__ == "__main__":
    # A clean 5-wave uptrend (100->140) followed by an a-b-c correction down
    # to 112, with a lead-in so the origin is a real fractal.
    pivots = [106, 100, 110, 104, 130, 118, 140, 122, 132, 112, 120]
    df = _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.2, seed=3)

    swings = identify_swings(df, left=2, right=2, min_move=3.0)
    print(f"{len(swings)} confirmed swings")

    sequence = label_wave_sequence(swings)
    print(f"\n{len(sequence)} labeled points:")
    print(describe_sequence(sequence))
