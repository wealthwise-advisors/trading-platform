"""
triangle.py
===========

Measures Triangle candidates. Classifies nothing.

>>> THIS MODULE NEVER EMITS A STRUCTURE. <<<
``StructureType`` deliberately has no ``TRIANGLE`` member, and that absence is
the enforcement mechanism for OQ-12, asserted by TR-2.

WHAT THE REFERENCE ACTUALLY SAYS (section 5.3, re-verified 2026-08-10)
----------------------------------------------------------------------
  TRI-01  "Corrective structure labelled as ABCDE"          M, exact
  TRI-03  "Subdivided into three (3-3-3-3-3)"               M, exact
  TRI-02  "Usually happens in wave B or wave 4"             guideline
  TRI-05  "a sideways movement ... decreasing volume and volatility"
  TRI-06  "RSI also needs to support the triangle in every time frame"
  TRI-04  "Subdivision of ABCDE can be either abc, wxy, or flat"  permissive

Nothing about wave D or wave E. No Fibonacci ratio of any kind. Nothing about
what follows a triangle. The four variants -- ascending, descending,
contracting, expanding -- are NAMED AND NOTHING ELSE: the distinguishing
geometry appears only in a graphic, never in prose. That is a stronger gap
than "unquantified"; there is no text to extract.

WHY TRI-01 + TRI-03 DO NOT GATE
-------------------------------
Both are mandatory-tier and exact, the same signature FLE-01 has, and they are
genuinely selective -- 328 of 3,912 five-leg windows (8.4%) pass, comparable
to the flat and zigzag confirm rates. An earlier note called this gate
"near-vacuous"; that was measured and is wrong. It still does not gate, for
three reasons:

  1. The strict reading of "subdivided into three" -- exactly three finer legs
     per side -- yields ONE candidate across all 3,912 windows. The 328 come
     from the loose predicate diagonal.py already uses, so Triangle inherits
     OQ-25 rather than standing on its own.
  2. Nothing can constrain WHERE a triangle occurs. TRI-02 is worded
     "usually", which is guideline grammar, and it is moot regardless: only 6
     of the 328 candidates sit in an impulse wave 4 or a zigzag/flat wave B.
  3. The reference's own definition opens "a triangle is a sideways
     movement", and 21% of candidates have net displacement above 50% of
     their path length -- plainly trending. No threshold for "sideways" is
     derivable: the ratio is a broad plateau (p25 0.160, p50 0.312, p75
     0.479) whose apparent modes were rejected by bootstrap, 0 of 3 stable.

That third point is what separates this from FLE-01. FLE-01 is a complete
criterion for what it claims; TRI-01 + TRI-03 is an INCOMPLETE criterion for
"triangle", because the definitional content of the word is exactly what it
omits. Emitting a structure named TRIANGLE for a plainly trending move would
be worse than emitting nothing.

Related: 3-3-3-3-3 is also an explicitly permitted DIAGONAL shape (LD-03 /
ED-03). Measured overlap between these candidates and confirmed diagonals is
zero -- diagonals are enumerated only inside impulse wave-1/wave-5 hosts, a
different basis -- but the principle stands: with no gateable host rule, a
triangle would be defined as "a 3-3-3-3-3 that is not inside an impulse
host", which is a definition by exclusion the reference never gives.
"""

from __future__ import annotations

import pandas as pd

from . import hierarchy
from .models import Pivot

#: TRI-01: "labelled as ABCDE" -- five sides, so six boundary pivots.
TRIANGLE_SIDES = 5

#: OQ-12 blocks naming a variant and quantifying "sideways"; OQ-13 blocks
#: deciding whether RSI "supports". Both are recorded on every candidate.
TRIANGLE_BLOCKED_BY = ("OQ-12", "OQ-13")


def _subdivision_counts(
    span: list[Pivot],
    finer_pivots: list[Pivot],
) -> list[int]:
    """Finer-scale legs inside each side of the candidate."""
    counts = []
    for a, b in zip(span, span[1:]):
        inside = sum(1 for p in finer_pivots if a.index <= p.index <= b.index)
        counts.append(max(0, inside - 1))
    return counts


def _is_three_three_three_three_three(
    span: list[Pivot],
    counts: list[int],
    finer_scale: int,
    spans: hierarchy.SpanIndex,
) -> bool:
    """TRI-03, read exactly as diagonal.py reads LD-03/ED-03's 3-3-3-3-3.

    Using the same predicate is deliberate: the reference states the identical
    shape for both, so reading it two different ways would be inventing a
    distinction. Both readings live under OQ-25.
    """
    for a, b in zip(span, span[1:]):
        if spans.contains(finer_scale, "five_wave", a.index, b.index):
            return False
    return all(n >= 2 for n in counts)


def _sidewaysness(prices: list[float]) -> float | None:
    """Net displacement over total path length.

    0.0 is a perfect round trip, 1.0 a straight line. Recorded because TRI-05
    calls a triangle "a sideways movement"; NOT compared against anything,
    because no threshold for that phrase exists in the reference or in the
    data (OQ-12).
    """
    path = sum(abs(b - a) for a, b in zip(prices, prices[1:]))
    if path == 0:
        return None
    return abs(prices[-1] - prices[0]) / path


def _slope(p0: Pivot, p1: Pivot) -> float | None:
    """Price change per bar between two pivots."""
    bars = p1.index - p0.index
    if bars == 0:
        return None
    return (p1.price - p0.price) / bars


def _rsi_at_pivots(span: list[Pivot], rsi: pd.Series) -> list[float | None]:
    """TRI-06's input, without TRI-06's verdict.

    "RSI also needs to support the triangle in every time frame" states no
    direction, no threshold and no comparison, and "every time frame" has no
    meaning in a single-timeframe engine. So the readings are reported and
    "supports" is never decided (OQ-13).
    """
    out: list[float | None] = []
    for p in span:
        if 0 <= p.index < len(rsi):
            v = rsi.iloc[p.index]
            out.append(float(v) if v == v else None)
        else:
            out.append(None)
    return out


def measure_candidates(
    pivots_by_scale: dict[int, list[Pivot]],
    spans: hierarchy.SpanIndex,
    rsi: pd.Series,
) -> list[dict]:
    """Every window satisfying TRI-01 and TRI-03, measured and left unnamed.

    Returns plain dicts, not ``Wave`` objects, precisely because these are not
    structures: promoting them to waves would put an unclassifiable shape into
    the same list the chart renders as confirmed analysis.
    """
    records: list[dict] = []
    for scale in sorted(pivots_by_scale):
        finer_scale = scale - 1
        if finer_scale < 1:
            continue
        finer = pivots_by_scale.get(finer_scale, [])
        if not finer:
            continue
        ps = pivots_by_scale[scale]
        for i in range(len(ps) - TRIANGLE_SIDES):
            span = ps[i:i + TRIANGLE_SIDES + 1]
            counts = _subdivision_counts(span, finer)
            if not _is_three_three_three_three_three(span, counts, finer_scale, spans):
                continue

            prices = [p.price for p in span]
            records.append({
                "scale": scale,
                "start_index": span[0].index,
                "end_index": span[-1].index,
                # the pivot that confirms the whole window -- consumers must
                # not treat a candidate as known before this bar
                "confirm_index": span[-1].confirm_index,
                "TRI-01_sides": TRIANGLE_SIDES,
                "TRI-03_subdivision_counts": counts,
                # TRI-05's "sideways movement", quantified but never judged
                "TRI-05_net_over_path": _sidewaysness(prices),
                # the two trendlines that WOULD name the four variants, if the
                # reference described them anywhere but in a graphic
                "TRI-07_slope_A_C_E": _slope(span[0], span[4]),
                "TRI-07_slope_B_D": _slope(span[1], span[3]),
                "TRI-06_rsi_at_pivots": _rsi_at_pivots(span, rsi),
                "blocked_by": list(TRIANGLE_BLOCKED_BY),
            })
    return records
