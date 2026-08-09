"""
hierarchy.py
============

Turns scale-tagged pivot lists into the leg windows the structure detectors
consume, and answers containment questions across scales.

Two SRS points this module exists to honour:

* FR-1d.4 -- cross-scale nesting is NOT assumed. Directional change at a
  coarse threshold does not guarantee its extremes are a subset of a finer
  threshold's. Measured containment on real CL/ES data is 99-100%, but 99% is
  not 100%, so ``containment_rate`` reports the real figure rather than
  asserting one, and nothing here breaks when a coarse pivot has no finer
  twin.

* FR-1d.3 -- ``scale`` is an integer ladder index, NOT an Elliott degree.
  Mapping scales onto the reference's 9 named degrees is OQ-17, still open.
  This module never assigns a degree name.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right

from .models import Direction, Pivot, PivotKind


def windows(pivots: list[Pivot], legs: int):
    """Yield every contiguous window of ``legs`` legs (legs + 1 pivots).

    Pivots alternate high/low by construction (FR-1c.2), so a contiguous slice
    is always a well-formed alternating sequence.
    """
    need = legs + 1
    for i in range(0, max(0, len(pivots) - need + 1)):
        yield pivots[i:i + need]


def direction_of(window: list[Pivot]) -> Direction:
    """A window rising off a LOW is an up-move; off a HIGH, a down-move."""
    return Direction.UP if window[0].kind is PivotKind.LOW else Direction.DOWN


class SpanIndex:
    """Fast 'is there a structure of type X fully inside [a, b]?' lookups.

    Structures are registered per scale as (start_index, end_index) spans.
    Queries are used by IMP-02 (waves 1/3/5 subdivide into impulses), ZZ-02
    (waves A and C subdivide into 5 waves) and FL-02 (wave A subdivides into 3).
    """

    def __init__(self) -> None:
        self._spans: dict[tuple[int, str], list[tuple[int, int]]] = {}
        self._starts: dict[tuple[int, str], list[int]] = {}

    def add(self, scale: int, kind: str, start_index: int, end_index: int) -> None:
        key = (scale, kind)
        self._spans.setdefault(key, []).append((start_index, end_index))

    def freeze(self) -> None:
        """Sort spans by start so lookups can bisect. Call once per scale pass."""
        for key, spans in self._spans.items():
            spans.sort()
            self._starts[key] = [s for s, _ in spans]

    def contains(self, scale: int, kind: str, a: int, b: int) -> bool:
        """True if any registered span of ``kind`` at ``scale`` fits in [a, b]."""
        key = (scale, kind)
        spans = self._spans.get(key)
        if not spans:
            return False
        starts = self._starts.get(key)
        if starts is None:            # not frozen -- fall back to a linear scan
            return any(s >= a and e <= b for s, e in spans)
        lo = bisect_left(starts, a)
        hi = bisect_right(starts, b)
        for i in range(lo, hi):
            s, e = spans[i]
            if e <= b:
                return True
        return False


def pivots_inside(pivots: list[Pivot], a: int, b: int) -> list[Pivot]:
    """Pivots strictly inside the open bar interval (a, b)."""
    return [p for p in pivots if a < p.index < b]


def containment_rate(coarse: list[Pivot], fine: list[Pivot]) -> float | None:
    """Share of coarse pivots whose bar is also a fine pivot's bar.

    Reported, never assumed (FR-1d.4 / TR-7b). Returns None when either scale
    is empty.
    """
    if not coarse or not fine:
        return None
    fine_bars = {p.index for p in fine}
    hits = sum(1 for p in coarse if p.index in fine_bars)
    return hits / len(coarse)
