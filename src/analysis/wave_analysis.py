"""
wave_analysis.py
================

Capstone: an INTEGRATED, in-depth Elliott wave analyzer that orchestrates every
other module into one read of the market.

Pipeline per call
------------------
  swing_identification  -> confirmed pivots + structure (HH/HL/LH/LL, trend)
  wave_numbering         -> continuous chart-wide wave count (Wave 1, 2.1, 3.1...)
  elliott_wave          -> validated impulse (hard rules), single best window
  corrective_waves      -> the following correction's type (zigzag/flat/combo)
  fibonacci             -> proportion quality + projected confluence zones
  -> a WaveAnalysis: cycle position, bias, invalidation, target zones, ALTERNATES

Depth features
--------------
* Multi-degree (fractal) analysis: run detection at coarse ("primary") and fine
  ("minor") sensitivity and relate sub-waves to their parent wave.
* Alternate counts: Elliott is probabilistic; we surface competing reads and the
  price that invalidates the primary one, rather than pretending to one answer.

Honesty: every output is a CANDIDATE read to be confirmed or invalidated by
subsequent price. Structure + Fibonacci raise the odds; they do not remove risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .swing_identification import (
    Swing, SwingType, identify_swings, trend_state, atr,
)
from .elliott_wave import ImpulseWave, find_impulses
from .corrective_waves import (
    Correction, CorrectionType, classify_abc, find_combinations,
)
from .fibonacci import (
    score_impulse_fib, score_correction_fib, correction_end_zone,
    project_correction_c, fib_projections, find_confluence, ClusterZone,
)
from .wave_numbering import WaveLabel, label_wave_sequence


@dataclass
class WaveAnalysis:
    degree: str
    trend: str
    n_swings: int
    impulse: Optional[ImpulseWave]
    impulse_fib: Optional[dict]
    correction: Optional[Correction]
    correction_fib: Optional[dict]
    cycle_position: str
    bias: str
    invalidation: Optional[float]
    target_zones: List[ClusterZone] = field(default_factory=list)
    alternates: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    wave_sequence: List[WaveLabel] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Locate the correction that follows an impulse
# --------------------------------------------------------------------------- #
def _find_correction(swings: List[Swing], impulse: ImpulseWave) -> Optional[Correction]:
    """The correction that begins at the impulse's terminal pivot (P5)."""
    last = impulse.pivots[-1]
    pos = next((k for k, s in enumerate(swings)
                if s.index == last.index and s.kind == last.kind), None)
    if pos is None:
        return None

    # prefer a complex combination that starts exactly here
    for combo in find_combinations(swings):
        if combo.pivots[0].index == last.index:
            return combo

    # else a simple ABC from the next 4 pivots (S=P5, A, B, C)
    if pos + 4 <= len(swings):
        return classify_abc(swings[pos:pos + 4])
    return None


# --------------------------------------------------------------------------- #
# Interpretation: cycle position / bias / invalidation / alternates
# --------------------------------------------------------------------------- #
def _interpret(impulse, correction, price, trend):
    notes, alternates = [], []

    if impulse is None:
        bias = {"uptrend": "long", "downtrend": "short"}.get(trend, "neutral")
        return (f"no validated impulse at this degree; structure = {trend}",
                bias, None, alternates, notes)

    P = [p.price for p in impulse.pivots]
    origin, top = P[0], P[5]
    dirn = impulse.direction
    invalidation = origin  # breaching wave-1 origin voids the count

    if correction is None:
        pos = f"{dirn}-impulse complete (W1-W5); no correction detected yet"
        bias = "neutral"
        notes.append("impulse done -> expect a correction before resumption; stand aside or fade with care")
        alternates.append("wave 5 may still be extending; a new high/low would push the W5 label out")
    else:
        ctype = correction.type.value
        pos = f"{dirn}-impulse complete; corrective '{ctype}' in progress"
        # after a correction we expect the impulse direction to resume
        bias = "long" if dirn == "up" else "short"
        notes.append(f"trade the resumption {bias.upper()} as the correction completes near a support/target zone")
        if correction.type == CorrectionType.ZIGZAG:
            alternates.append("sharp zigzag -> strong resumption likely; but it may be wave A of a larger flat")
        elif "flat" in ctype:
            alternates.append("flat/expanded -> sideways; could morph into a triangle or a double three")
        else:
            alternates.append("complex correction -> more sideways time possible before resumption")
        alternates.append(f"if price breaches origin {origin:.2f}, the impulse count is invalidated")

    return pos, bias, invalidation, alternates, notes


# --------------------------------------------------------------------------- #
# Single-degree analysis
# --------------------------------------------------------------------------- #
def analyze(df: pd.DataFrame, left: int = 2, right: int = 2,
            min_move: float = 0.0, degree: str = "minor") -> WaveAnalysis:
    swings = identify_swings(df, left=left, right=right, min_move=min_move)
    trend = trend_state(swings)
    wave_sequence = label_wave_sequence(swings)

    valid = [w for w in find_impulses(swings) if w.valid]
    impulse = max(valid, key=lambda w: w.end_index) if valid else None
    impulse_fib = score_impulse_fib(impulse) if impulse else None

    correction = _find_correction(swings, impulse) if impulse else None
    correction_fib = (score_correction_fib(correction)
                      if correction and correction.type in
                      (CorrectionType.ZIGZAG, CorrectionType.REGULAR_FLAT,
                       CorrectionType.EXPANDED_FLAT, CorrectionType.RUNNING_FLAT)
                      else None)

    price = float(df["close"].iloc[-1])
    cycle, bias, invalidation, alternates, notes = _interpret(
        impulse, correction, price, trend)

    # ---- confluence target zones (mingle impulse + corrective levels) ----
    zones: List[ClusterZone] = []
    if impulse:
        P = [p.price for p in impulse.pivots]
        origin, top = P[0], P[5]
        levels = []
        for r, px in correction_end_zone(origin, top).items():
            levels.append((px, f"impulse-retr {int(r*100)}%"))
        if correction and len(correction.pivots) >= 3:
            S, A, B = (p.price for p in correction.pivots[:3])
            for r, px in project_correction_c(S, A, B).items():
                levels.append((px, f"C x{r}"))
        # resumption targets: project the impulse length beyond its top
        for r, px in fib_projections(top, origin, top, ratios=[0.618, 1.0, 1.618]).items():
            levels.append((px, f"cont x{r}"))
        zones = find_confluence(levels, tol_frac=0.01)

        # surface nearest support / target relative to current price
        below = [z for z in zones if z.center < price]
        above = [z for z in zones if z.center > price]
        if below:
            nz = max(below, key=lambda z: z.center)
            notes.append(f"nearest support confluence ~{nz.center} (strength {nz.strength})")
        if above:
            nz = min(above, key=lambda z: z.center)
            notes.append(f"nearest target confluence ~{nz.center} (strength {nz.strength})")

    return WaveAnalysis(
        degree=degree, trend=trend, n_swings=len(swings),
        impulse=impulse, impulse_fib=impulse_fib,
        correction=correction, correction_fib=correction_fib,
        cycle_position=cycle, bias=bias, invalidation=invalidation,
        target_zones=zones, alternates=alternates, notes=notes,
        wave_sequence=wave_sequence,
    )


# --------------------------------------------------------------------------- #
# Multi-degree (fractal) analysis
# --------------------------------------------------------------------------- #
def analyze_degrees(df: pd.DataFrame, degrees=None) -> dict:
    """Run analysis at several sensitivities. Coarse = larger waves, fine = sub-waves."""
    if degrees is None:
        degrees = [
            {"name": "primary", "left": 4, "right": 4, "mm_mult": 2.0},
            {"name": "minor",   "left": 2, "right": 2, "mm_mult": 1.0},
        ]
    med = float(np.nanmedian(atr(df["high"], df["low"], df["close"], 14)))
    return {d["name"]: analyze(df, d["left"], d["right"], d["mm_mult"] * med, d["name"])
            for d in degrees}


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def describe(a: WaveAnalysis) -> str:
    lines = [f"[{a.degree}]  trend={a.trend}  swings={a.n_swings}",
             f"  cycle : {a.cycle_position}",
             f"  bias  : {a.bias}"
             + (f"   invalidation<{a.invalidation:.2f}" if a.invalidation else "")]
    if a.impulse:
        P = [round(p.price, 1) for p in a.impulse.pivots]
        lines.append(f"  impulse: {a.impulse.direction} bars "
                     f"{a.impulse.start_index}->{a.impulse.end_index}  "
                     f"pivots={P}  fib_fit={a.impulse_fib['fib_fit']}")
    if a.correction:
        cf = a.correction_fib["fib_fit"] if a.correction_fib else "n/a"
        lines.append(f"  correction: {a.correction.type.value} "
                     f"bars {a.correction.start_index}->{a.correction.end_index}  fib_fit={cf}")
    if a.target_zones:
        top = sorted(a.target_zones, key=lambda z: z.strength, reverse=True)[:3]
        lines.append("  target zones: " + " | ".join(
            f"{z.center}(x{z.strength})" for z in top))
    for n in a.notes:
        lines.append(f"  note  : {n}")
    for alt in a.alternates:
        lines.append(f"  alt   : {alt}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.15, seed=3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = []
    for a, b in zip(pivots, pivots[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivots[-1])
    closes = np.asarray(closes) + rng.normal(0, noise, len(closes))
    return pd.DataFrame({"high": closes + rng.uniform(0.1, 0.4, len(closes)),
                         "low": closes - rng.uniform(0.1, 0.4, len(closes)),
                         "close": closes})


if __name__ == "__main__":
    # a full cycle: up-impulse 100->140, then an ABC correction down to 112
    pivots = [106, 100, 110, 104, 130, 118, 140, 122, 132, 112, 120]
    df = _ohlc_from_pivots(pivots, bars_per_leg=9)

    print("================ SINGLE-DEGREE, IN-DEPTH ================")
    med = float(np.nanmedian(atr(df["high"], df["low"], df["close"], 14)))
    print(describe(analyze(df, left=2, right=2, min_move=med, degree="minor")))

    print("\n================ MULTI-DEGREE (FRACTAL) ================")
    degs = analyze_degrees(df)
    for name, a in degs.items():
        print(describe(a))
        print()

    # relate degrees: how many minor sub-pivots fall inside the primary impulse?
    prim, minor = degs["primary"], degs["minor"]
    if prim.impulse:
        lo, hi = prim.impulse.start_index, prim.impulse.end_index
        subs = [s for s in identify_swings(df, 2, 2, med) if lo <= s.index <= hi]
        print(f"fractal link: primary impulse spans bars {lo}-{hi}; "
              f"minor degree finds {len(subs)} sub-pivots inside it")

    print("\nNOTE: candidate reads only -- confirm/invalidate with subsequent price;"
          " not financial advice.")
