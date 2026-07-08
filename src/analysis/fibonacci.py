"""
fibonacci.py
============

Fibonacci integration across impulse and corrective waves.

Two roles, then the payoff:

  1. MEASURING STICK  -- score how closely each wave's realised proportion
     matches its ideal Fibonacci ratio. A rule-valid impulse whose waves also
     hit 0.618 / 1.618 / 0.382 is higher-conviction than one that merely passes.

  2. TARGET PROJECTOR -- from the waves formed so far, project where the NEXT
     wave (or the correction's end) is likely to terminate.

  3. CONFLUENCE (the point) -- overlay impulse targets and corrective
     retracements; where several independent levels cluster, you get a
     high-probability reaction zone for entries / exits.

Honesty: Fibonacci relationships are GUIDELINES, not laws. Waves miss them
often; clusters raise probability, they do not guarantee a turn. The confluence
tolerance is a tunable -- loosen it and everything "clusters"; keep it tight.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .swing_identification import Swing, SwingType
from .elliott_wave import ImpulseWave
from .corrective_waves import Correction, CorrectionType


# Standard ratio menus -------------------------------------------------------
RETRACE = [0.236, 0.382, 0.5, 0.618, 0.786]
PROJECT = [0.618, 1.0, 1.618, 2.618, 4.236]

# Per-wave ideal sets --------------------------------------------------------
IDEAL_IMPULSE = {
    "w2_of_w1": [0.382, 0.5, 0.618, 0.786],
    "w3_of_w1": [1.618, 2.618, 4.236],
    "w4_of_w3": [0.236, 0.382, 0.5],
    "w5_of_w1": [0.618, 1.0, 1.618],
}
IDEAL_CORRECTION = {
    CorrectionType.ZIGZAG:        {"b_of_a": [0.382, 0.5, 0.618, 0.786], "c_of_a": [1.0, 1.618]},
    CorrectionType.REGULAR_FLAT:  {"b_of_a": [0.9, 1.0], "c_of_a": [1.0, 1.382]},
    CorrectionType.EXPANDED_FLAT: {"b_of_a": [1.236, 1.382], "c_of_a": [1.382, 1.618]},
    CorrectionType.RUNNING_FLAT:  {"b_of_a": [1.236, 1.382], "c_of_a": [0.618, 1.0]},
}


# --------------------------------------------------------------------------- #
# Core Fibonacci math
# --------------------------------------------------------------------------- #
def fib_retracements(p0: float, p1: float, ratios=RETRACE) -> Dict[float, float]:
    """Retracement price levels of the move p0 -> p1 (p1 is the extreme).
    Works both directions: r=0 sits at p1, r=1 sits at p0."""
    return {r: round(p1 - r * (p1 - p0), 4) for r in ratios}


def fib_projections(anchor: float, leg_from: float, leg_to: float,
                    ratios=PROJECT) -> Dict[float, float]:
    """Project a leg of vector (leg_to - leg_from) from ``anchor`` at each ratio."""
    leg = leg_to - leg_from
    return {r: round(anchor + r * leg, 4) for r in ratios}


def nearest_fib(value: float, table: List[float]) -> Tuple[float, float]:
    """Nearest ideal ratio to ``value`` and the absolute distance."""
    best = min(table, key=lambda t: abs(value - t))
    return best, round(abs(value - best), 4)


def _fit(dist: float, cap: float = 0.25) -> float:
    """Turn a ratio distance into a 0..1 closeness score."""
    return max(0.0, 1.0 - dist / cap)


# --------------------------------------------------------------------------- #
# Impulse: score realised ratios + project the next wave
# --------------------------------------------------------------------------- #
def score_impulse_fib(w: ImpulseWave) -> dict:
    P = [p.price for p in w.pivots]
    w1, w2 = abs(P[1] - P[0]), abs(P[1] - P[2])
    w3, w4 = abs(P[3] - P[2]), abs(P[3] - P[4])
    w5 = abs(P[5] - P[4])
    achieved = {
        "w2_of_w1": w2 / w1 if w1 else 0,
        "w3_of_w1": w3 / w1 if w1 else 0,
        "w4_of_w3": w4 / w3 if w3 else 0,
        "w5_of_w1": w5 / w1 if w1 else 0,
    }
    detail, scores = {}, []
    for key, val in achieved.items():
        lvl, dist = nearest_fib(val, IDEAL_IMPULSE[key])
        detail[key] = {"achieved": round(val, 3), "nearest_ideal": lvl, "dist": dist}
        scores.append(_fit(dist))
    return {"fib_fit": round(float(np.mean(scores)), 3), "detail": detail}


def project_wave3(p0: float, p1: float, p2: float) -> Dict[float, float]:
    """Wave-3 targets: extend wave 1 (p1-p0) from the wave-2 pivot p2."""
    return fib_projections(anchor=p2, leg_from=p0, leg_to=p1,
                           ratios=[1.0, 1.618, 2.618, 4.236])


def project_wave5(p0: float, p1: float, p2: float, p3: float, p4: float) -> Dict[str, float]:
    """Wave-5 targets from common relationships."""
    w1 = p1 - p0
    net13 = p3 - p0
    return {
        "= w1 (x1.0)":      round(p4 + 1.0 * w1, 4),
        "w1 x1.618":        round(p4 + 1.618 * w1, 4),
        "0.618 of net 1-3": round(p4 + 0.618 * net13, 4),
        "1.0 of net 1-3":   round(p4 + 1.0 * net13, 4),
    }


# --------------------------------------------------------------------------- #
# Correction: score + project C and the correction-end retracement
# --------------------------------------------------------------------------- #
def score_correction_fib(c: Correction) -> dict:
    if c.type not in IDEAL_CORRECTION or len(c.pivots) < 4:
        return {"fib_fit": None, "detail": {}}
    S, A, B, Cc = (p.price for p in c.pivots[:4])
    leg_a = abs(A - S)
    b_of_a = abs(B - A) / leg_a if leg_a else 0
    c_of_a = abs(Cc - B) / leg_a if leg_a else 0
    ideals = IDEAL_CORRECTION[c.type]
    detail, scores = {}, []
    for key, val in (("b_of_a", b_of_a), ("c_of_a", c_of_a)):
        lvl, dist = nearest_fib(val, ideals[key])
        detail[key] = {"achieved": round(val, 3), "nearest_ideal": lvl, "dist": dist}
        scores.append(_fit(dist))
    return {"fib_fit": round(float(np.mean(scores)), 3), "detail": detail}


def project_correction_c(S: float, A: float, B: float) -> Dict[float, float]:
    """Wave-C targets: project wave A (A-S) from the B pivot."""
    return fib_projections(anchor=B, leg_from=S, leg_to=A, ratios=[0.618, 1.0, 1.618])


def correction_end_zone(impulse_p0: float, impulse_p5: float) -> Dict[float, float]:
    """Where a correction of a completed impulse is likely to end:
    the 38.2 / 50 / 61.8% retracement of the whole impulse."""
    return fib_retracements(impulse_p0, impulse_p5, ratios=[0.382, 0.5, 0.618])


# --------------------------------------------------------------------------- #
# Confluence: merge levels from different sources into reaction zones
# --------------------------------------------------------------------------- #
@dataclass
class ClusterZone:
    center: float
    low: float
    high: float
    members: List[Tuple[float, str]]

    @property
    def strength(self) -> int:
        return len(self.members)


def find_confluence(levels: List[Tuple[float, str]], tol_frac: float = 0.006) -> List[ClusterZone]:
    """Cluster nearby price levels (from any source) into confluence zones.

    ``levels`` is a list of (price, source_label). A zone's strength is how many
    independent levels fall within ``tol_frac`` of its running center.
    """
    pts = sorted(levels, key=lambda t: t[0])
    zones, cur = [], []
    for price, label in pts:
        if not cur:
            cur = [(price, label)]
            continue
        center = np.mean([p for p, _ in cur])
        if abs(price - center) <= tol_frac * center:
            cur.append((price, label))
        else:
            zones.append(cur)
            cur = [(price, label)]
    if cur:
        zones.append(cur)

    out = []
    for z in zones:
        ps = [p for p, _ in z]
        out.append(ClusterZone(round(float(np.mean(ps)), 3), min(ps), max(ps), z))
    return sorted(out, key=lambda z: z.strength, reverse=True)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _mk(idx, price, kind):
    return Swing(idx, idx + 2, price, kind)


if __name__ == "__main__":
    from elliott_wave import find_impulses
    H, L = SwingType.HIGH, SwingType.LOW

    # the clean impulse from the elliott_wave demo: 100 -> 140
    swings = [_mk(8, 100, L), _mk(16, 110, H), _mk(24, 104, L),
              _mk(32, 130, H), _mk(40, 118, L), _mk(48, 140, H)]
    impulse = find_impulses(swings)[0]

    print("=== impulse Fibonacci fit ===")
    sf = score_impulse_fib(impulse)
    print(f"  fib_fit = {sf['fib_fit']}")
    for k, v in sf["detail"].items():
        print(f"    {k:<9} achieved {v['achieved']:<6} ~ ideal {v['nearest_ideal']}  (dist {v['dist']})")

    P = [p.price for p in impulse.pivots]
    print("\n=== forward projections ===")
    print("  wave-5 targets:", project_wave5(*P[:5]))
    print("  correction-end zone (retrace of impulse):", correction_end_zone(P[0], P[5]))
    print("  wave-C targets (A=140->122, B=132):", project_correction_c(140, 122, 132))

    print("\n=== confluence (mingling impulse + corrective levels) ===")
    levels: list = []
    for r, px in project_wave5(*P[:5]).items() if False else []:
        levels.append((px, f"w5 {r}"))
    for lbl, px in project_wave5(*P[:5]).items():
        levels.append((px, f"w5:{lbl}"))
    for r, px in correction_end_zone(P[0], P[5]).items():
        levels.append((px, f"impulse-retr {int(r*100)}%"))
    for r, px in project_correction_c(140, 122, 132).items():
        levels.append((px, f"C x{r}"))

    for z in find_confluence(levels, tol_frac=0.01):
        tag = "  <-- CONFLUENCE" if z.strength >= 2 else ""
        srcs = ", ".join(s for _, s in z.members)
        print(f"  {z.center:>8}  strength={z.strength}  [{srcs}]{tag}")

    print("\nNOTE: Fib levels are guidelines; confluence raises probability, not certainty.")
