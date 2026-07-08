"""
elliott_wave.py
===============

Rule-based Elliott Wave analysis built on top of ``swing_identification``.

Philosophy
----------
Elliott Wave done by hand is subjective -- the same chart gets counted many
ways and counts get revised after the fact. To make it *systematic* we never
"guess the count". Instead we take the confirmed, alternating swing pivots and
ask a mechanical question: does this 6-pivot window form a STRUCTURALLY LEGAL
impulse? Validity is decided by Elliott's three inviolable rules; Fibonacci
proportions are a soft confidence score, not a gate.

Impulse (up) = pivots  L0 H1 L2 H3 L4 H5   (waves 1..5 = the five legs)
Impulse (down) = the mirror,  H0 L1 H2 L3 H4 L5

The three hard rules
--------------------
1. Wave 2 never retraces beyond the start of wave 1.
2. Wave 3 is never the shortest of waves 1, 3, 5.
3. Wave 4 does not enter wave 1's price territory (standard impulse).

Scope / honesty
---------------
This validates the *classic* impulse and a simple ABC zigzag only. It does NOT
model extensions, diagonals, truncations beyond a flag, or complex corrections
(flats, triangles, combinations). Treat a "valid" result as a rule-checked
candidate to act on with confirmation -- not as ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple

import numpy as np
import pandas as pd

from .swing_identification import (
    Swing, SwingType, identify_swings, swings_to_frame, atr,
)

Direction = Literal["up", "down"]


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class ImpulseWave:
    direction: Direction
    pivots: List[Swing]      # exactly 6: P0 (origin) .. P5
    valid: bool              # all hard rules passed
    rules: dict              # rule_name -> bool, for transparency
    fib_score: float         # 0..1, closeness to Fibonacci guidelines
    truncated_fifth: bool    # wave 5 failed to exceed wave 3

    @property
    def start_index(self) -> int:
        return self.pivots[0].index

    @property
    def end_index(self) -> int:
        return self.pivots[-1].index

    @property
    def confirm_index(self) -> int:
        # the pattern is only knowable once its last pivot is confirmed
        return self.pivots[-1].confirm_index


@dataclass
class ZigzagABC:
    direction: Direction     # direction of the correction itself
    pivots: List[Swing]      # 4: X (prior extreme), A, B, C
    valid: bool
    rules: dict


# --------------------------------------------------------------------------- #
# Impulse validation
# --------------------------------------------------------------------------- #
_UP_KINDS = [SwingType.LOW, SwingType.HIGH, SwingType.LOW,
             SwingType.HIGH, SwingType.LOW, SwingType.HIGH]
_DN_KINDS = [SwingType.HIGH, SwingType.LOW, SwingType.HIGH,
             SwingType.LOW, SwingType.HIGH, SwingType.LOW]


def _check_impulse(window: List[Swing], direction: Direction) -> Tuple[bool, dict, bool]:
    """Apply Elliott's hard rules to a 6-pivot window. Returns (valid, rules, truncated)."""
    P = [s.price for s in window]
    kinds = [s.kind for s in window]

    if direction == "up":
        kinds_ok = kinds == _UP_KINDS
        len1, len3, len5 = P[1] - P[0], P[3] - P[2], P[5] - P[4]
        rules = {
            "alternation":        kinds_ok,
            "w2_holds_origin":    P[2] > P[0],                 # rule 1
            "w3_exceeds_w1":      P[3] > P[1],                 # impulse extends
            "w3_not_shortest":    not (len3 < len1 and len3 < len5),  # rule 2
            "w4_no_overlap_w1":   P[4] > P[1],                 # rule 3
        }
        truncated = P[5] <= P[3]
    else:
        kinds_ok = kinds == _DN_KINDS
        len1, len3, len5 = P[0] - P[1], P[2] - P[3], P[4] - P[5]
        rules = {
            "alternation":        kinds_ok,
            "w2_holds_origin":    P[2] < P[0],
            "w3_exceeds_w1":      P[3] < P[1],
            "w3_not_shortest":    not (len3 < len1 and len3 < len5),
            "w4_no_overlap_w1":   P[4] < P[1],
        }
        truncated = P[5] >= P[3]

    return all(rules.values()), rules, truncated


def _fib_score(P: List[float]) -> float:
    """Soft 0..1 score: how close wave proportions are to Fibonacci guidelines.

    Guidelines (not rules): wave 2 retraces ~0.5-0.618 of wave 1; wave 4 retraces
    ~0.236-0.382 of wave 3; wave 3 extends ~1.618x (or more) of wave 1.
    """
    w1, w3, w5 = abs(P[1] - P[0]), abs(P[3] - P[2]), abs(P[5] - P[4])
    w2, w4 = abs(P[1] - P[2]), abs(P[3] - P[4])
    r2 = w2 / w1 if w1 else 0.0
    r4 = w4 / w3 if w3 else 0.0
    r3 = w3 / w1 if w1 else 0.0

    def near(x: float, target: float) -> float:
        return max(0.0, 1.0 - abs(x - target) / target)

    s2 = max(near(r2, 0.5), near(r2, 0.618))
    s4 = max(near(r4, 0.382), near(r4, 0.236))
    s3 = near(min(r3, 2.618), 1.618)        # cap so huge extensions don't blow up
    return round((s2 + s4 + s3) / 3.0, 3)


def find_impulses(swings: List[Swing], require_valid: bool = True) -> List[ImpulseWave]:
    """Scan every 6-pivot window for legal impulses.

    Set ``require_valid=False`` to also return rule-failing candidates (useful
    for debugging why a count was rejected).
    """
    out: List[ImpulseWave] = []
    for i in range(len(swings) - 5):
        window = swings[i:i + 6]
        direction: Direction = "up" if window[0].kind == SwingType.LOW else "down"
        valid, rules, truncated = _check_impulse(window, direction)
        if valid or not require_valid:
            out.append(ImpulseWave(
                direction=direction,
                pivots=window,
                valid=valid,
                rules=rules,
                fib_score=_fib_score([s.price for s in window]),
                truncated_fifth=truncated,
            ))
    return out


# --------------------------------------------------------------------------- #
# ABC correction (simple zigzag)
# --------------------------------------------------------------------------- #
def find_corrections(swings: List[Swing]) -> List[ZigzagABC]:
    """Detect simple ABC zigzag corrections from 4-pivot windows (X, A, B, C)."""
    out: List[ZigzagABC] = []
    for i in range(len(swings) - 3):
        X, A, B, C = swings[i:i + 4]
        kinds = (X.kind, A.kind, B.kind, C.kind)

        if kinds == (SwingType.HIGH, SwingType.LOW, SwingType.HIGH, SwingType.LOW):
            rules = {"A_below_X": A.price < X.price,
                     "B_below_X": B.price < X.price,
                     "C_below_A": C.price < A.price}
            out.append(ZigzagABC("down", [X, A, B, C], all(rules.values()), rules))

        elif kinds == (SwingType.LOW, SwingType.HIGH, SwingType.LOW, SwingType.HIGH):
            rules = {"A_above_X": A.price > X.price,
                     "B_above_X": B.price > X.price,
                     "C_above_A": C.price > A.price}
            out.append(ZigzagABC("up", [X, A, B, C], all(rules.values()), rules))
    return out


# --------------------------------------------------------------------------- #
# Pretty print
# --------------------------------------------------------------------------- #
def describe_impulse(w: ImpulseWave) -> str:
    legs = " ".join(f"{'W'+str(k)}:{s.price:.1f}" if k else f"P0:{s.price:.1f}"
                    for k, s in enumerate(w.pivots))
    flags = []
    if w.truncated_fifth:
        flags.append("truncated-5th")
    failed = [k for k, v in w.rules.items() if not v]
    if failed:
        flags.append("fails:" + ",".join(failed))
    tag = "VALID" if w.valid else "invalid"
    return (f"[{tag}] {w.direction}-impulse  bars {w.start_index}->{w.end_index}  "
            f"confirm@{w.confirm_index}  fib={w.fib_score:.2f}  {legs}"
            + ("  <" + "; ".join(flags) + ">" if flags else ""))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.2, seed=1) -> pd.DataFrame:
    """Build a synthetic OHLC series that passes through the given pivot prices."""
    rng = np.random.default_rng(seed)
    closes = []
    for a, b in zip(pivots, pivots[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivots[-1])
    closes = np.asarray(closes) + rng.normal(0, noise, len(closes) + 0)[:len(closes)]
    high = closes + rng.uniform(0.1, 0.5, len(closes))
    low = closes - rng.uniform(0.1, 0.5, len(closes))
    return pd.DataFrame({"high": high, "low": low, "close": closes})


if __name__ == "__main__":
    # lead-in (106->100) so the origin low is a real fractal, a clean up impulse
    # 100->140, then an ABC down to 112, then a lead-out so C confirms.
    pivots = [106, 100, 110, 104, 130, 118, 140, 122, 132, 112, 120]
    df = _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.2, seed=3)

    swings = identify_swings(df, left=2, right=2, min_move=3.0)
    print("detected swings:")
    print(swings_to_frame(swings).to_string(index=False))

    impulses = find_impulses(swings, require_valid=False)
    print(f"\n{sum(w.valid for w in impulses)} valid / {len(impulses)} candidate impulses:")
    for w in impulses:
        print("  " + describe_impulse(w))

    corrections = find_corrections(swings)
    valid_abc = [c for c in corrections if c.valid]
    print(f"\n{len(valid_abc)} valid ABC zigzag(s):")
    for c in valid_abc:
        seq = " ".join(f"{lbl}:{s.price:.1f}" for lbl, s in zip("XABC", c.pivots))
        print(f"  [{c.direction}]  bars {c.pivots[0].index}->{c.pivots[-1].index}  {seq}")
