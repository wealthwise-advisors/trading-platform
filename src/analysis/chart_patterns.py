"""
chart_patterns.py
==================

Rule-based classic chart pattern detection built on the confirmed swing
pivots from swing_identification.py: Double Top, Double Bottom, Head &
Shoulders (regular and inverse). Triangle detection is already implemented
in corrective_waves.detect_triangle -- re-exported here for convenience so
callers have one place to get "all chart patterns."

Honesty: these are geometric pattern-matches on confirmed pivots, not a
forecast. A "detected" pattern is a candidate worth a second look, not a
signal to trade blind -- particularly Head & Shoulders, which is the most
subjective of the three and easiest to see in hindsight.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .swing_identification import Swing, SwingType, identify_swings
from .corrective_waves import detect_triangle  # re-exported


@dataclass
class ChartPattern:
    pattern: str                # "double_top" | "double_bottom" | "head_and_shoulders" | "inverse_head_and_shoulders"
    direction: str               # "bearish" (top patterns) / "bullish" (bottom patterns)
    pivots: List[Swing]
    neckline: float
    metrics: dict

    @property
    def start_index(self) -> int:
        return self.pivots[0].index

    @property
    def end_index(self) -> int:
        return self.pivots[-1].index


def _pct_diff(a: float, b: float) -> float:
    ref = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / ref


def find_double_top(swings: List[Swing], tolerance: float = 0.015, min_bar_gap: int = 6) -> List[ChartPattern]:
    """Scan H-L-H triplets where the two highs are within `tolerance` of each
    other and at least `min_bar_gap` bars apart (filters out trivial,
    immediately-adjacent "double tops" that are really just noise)."""
    out = []
    for i in range(len(swings) - 2):
        p0, p1, p2 = swings[i], swings[i + 1], swings[i + 2]
        if p0.kind == SwingType.HIGH and p1.kind == SwingType.LOW and p2.kind == SwingType.HIGH:
            if p2.index - p0.index < min_bar_gap:
                continue
            if _pct_diff(p0.price, p2.price) <= tolerance:
                out.append(ChartPattern(
                    pattern="double_top", direction="bearish",
                    pivots=[p0, p1, p2], neckline=p1.price,
                    metrics={"peak_diff_pct": round(_pct_diff(p0.price, p2.price) * 100, 2)},
                ))
    return out


def find_double_bottom(swings: List[Swing], tolerance: float = 0.015, min_bar_gap: int = 6) -> List[ChartPattern]:
    """Scan L-H-L triplets where the two lows are within `tolerance` of each
    other and at least `min_bar_gap` bars apart (filters out trivial,
    immediately-adjacent "double bottoms" that are really just noise)."""
    out = []
    for i in range(len(swings) - 2):
        p0, p1, p2 = swings[i], swings[i + 1], swings[i + 2]
        if p0.kind == SwingType.LOW and p1.kind == SwingType.HIGH and p2.kind == SwingType.LOW:
            if p2.index - p0.index < min_bar_gap:
                continue
            if _pct_diff(p0.price, p2.price) <= tolerance:
                out.append(ChartPattern(
                    pattern="double_bottom", direction="bullish",
                    pivots=[p0, p1, p2], neckline=p1.price,
                    metrics={"trough_diff_pct": round(_pct_diff(p0.price, p2.price) * 100, 2)},
                ))
    return out


def find_head_and_shoulders(
    swings: List[Swing],
    shoulder_tolerance: float = 0.02,
    neckline_tolerance: float = 0.02,
    min_head_prominence: float = 0.01,
) -> List[ChartPattern]:
    """Scan 5-pivot windows for regular (H-L-H-L-H, bearish) and inverse
    (L-H-L-H-L, bullish) Head & Shoulders. The middle pivot (the head) must
    be more extreme than both shoulders by at least `min_head_prominence`;
    the two shoulders and the two necklines must each be roughly level."""
    out = []
    for i in range(len(swings) - 4):
        window = swings[i:i + 5]
        kinds = [s.kind for s in window]
        s0, n0, head, n1, s1 = window

        if kinds == [SwingType.HIGH, SwingType.LOW, SwingType.HIGH, SwingType.LOW, SwingType.HIGH]:
            if _pct_diff(s0.price, s1.price) > shoulder_tolerance:
                continue
            if _pct_diff(n0.price, n1.price) > neckline_tolerance:
                continue
            shoulder_avg = (s0.price + s1.price) / 2
            prominence = (head.price - shoulder_avg) / shoulder_avg if shoulder_avg else 0
            if prominence < min_head_prominence:
                continue
            out.append(ChartPattern(
                pattern="head_and_shoulders", direction="bearish",
                pivots=window, neckline=(n0.price + n1.price) / 2,
                metrics={"head_prominence_pct": round(prominence * 100, 2),
                         "shoulder_diff_pct": round(_pct_diff(s0.price, s1.price) * 100, 2)},
            ))

        elif kinds == [SwingType.LOW, SwingType.HIGH, SwingType.LOW, SwingType.HIGH, SwingType.LOW]:
            if _pct_diff(s0.price, s1.price) > shoulder_tolerance:
                continue
            if _pct_diff(n0.price, n1.price) > neckline_tolerance:
                continue
            shoulder_avg = (s0.price + s1.price) / 2
            prominence = (shoulder_avg - head.price) / shoulder_avg if shoulder_avg else 0
            if prominence < min_head_prominence:
                continue
            out.append(ChartPattern(
                pattern="inverse_head_and_shoulders", direction="bullish",
                pivots=window, neckline=(n0.price + n1.price) / 2,
                metrics={"head_prominence_pct": round(prominence * 100, 2),
                         "shoulder_diff_pct": round(_pct_diff(s0.price, s1.price) * 100, 2)},
            ))

    return out


def find_chart_patterns(
    df, left: int = 2, right: int = 2, min_move: float = 0.0,
    double_tolerance: float = 0.015, double_min_bar_gap: int = 6,
    hs_shoulder_tolerance: float = 0.02,
) -> List[ChartPattern]:
    """One-call pipeline: identify swings, then scan for all supported patterns."""
    swings = identify_swings(df, left=left, right=right, min_move=min_move)
    patterns: List[ChartPattern] = []
    patterns += find_double_top(swings, tolerance=double_tolerance, min_bar_gap=double_min_bar_gap)
    patterns += find_double_bottom(swings, tolerance=double_tolerance, min_bar_gap=double_min_bar_gap)
    patterns += find_head_and_shoulders(swings, shoulder_tolerance=hs_shoulder_tolerance)
    return sorted(patterns, key=lambda p: p.start_index)
