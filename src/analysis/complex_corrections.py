"""
complex_corrections.py
=======================

Task 5 -- Triangle & Complex Correction CANDIDATE GENERATION for the
top-level continuous wave count. This module does not detect anything
itself; it scans the swing series for windows to hand to the ALREADY
EXISTING, UNMODIFIED detectors in ``corrective_waves.py``
(``detect_triangle``, ``find_combinations``, both reused verbatim per
explicit requirement) and turns a positive read into a plain
``CorrectiveCandidate`` that ``wave_numbering._generate_candidates`` can
adapt into a real ``_Candidate`` -- the same shape an impulse candidate
takes, so the unmodified DP-based selection (``_select_best_counts``) can
compare an impulse reading against a triangle/combination reading for the
same stretch of chart and pick whichever is genuinely stronger.

Why a separate module, not wave_numbering.py directly
-----------------------------------------------------
``WaveLabel``/``_Candidate`` live in wave_numbering.py, and that's also
where they get built (that module already has them in scope -- no import
needed there). This module stays independent of wave_numbering.py in BOTH
directions: it only imports from ``swing_identification`` and
``corrective_waves`` (neither of which imports wave_numbering.py either),
so there is no circular-import risk to manage, unlike the impulse detector
added for Task 4.

Why NOT gated by structure_classification.classify_structure
--------------------------------------------------------------
``_generate_candidates``'s existing impulse loop only offers a swing index
to ``_grow_count`` when the pre-numbering classifier says that point looks
like the start of a trending impulse -- ``POTENTIAL_TRIANGLE`` and
``POTENTIAL_COMPLEX_CORRECTION`` are reserved hypotheses there that always
score 0.0 (never implemented, per Tasks 2/3's explicit scope). Gating this
module's scan on that same classifier would mean these candidates could
NEVER be generated at all. Triangle/combination candidates are found
independently here, using ``detect_triangle``/``find_combinations``'s OWN
acceptance criteria as the only filter -- exactly how simple zigzag/flat
corrections are already found elsewhere in this codebase (via direct
``classify_abc`` calls, not through the impulse gate). Wiring
``structure_classification.py``'s reserved hypotheses to real detectors is
explicitly OUT of this task's scope (Task 5 only asked for top-level
candidate-generation integration) and is not attempted here -- see "Known
limitations" in the Task 5 response for this trade-off.

Quality, not correctness
--------------------------
Per requirement 5 ("if a structure is unsupported or ambiguous, return
UNKNOWN instead of forcing an incorrect Elliott count"): every candidate
here carries a ``quality`` score in [0, 1], and candidates below
``_MIN_QUALITY`` are discarded before they ever reach the candidate pool --
they never get to compete, let alone win, so a marginal/ambiguous fit can
never force a labeled count onto a stretch of chart. Nothing here overrides
``detect_triangle``'s or ``find_combinations``'s own pass/fail logic --
those are unchanged; a window that doesn't fit their criteria produces no
candidate at all, exactly as it did before this module existed.

Running triangle
-----------------
``detect_triangle`` only classifies "contracting" vs. "expanding" (do the
converging/diverging trendlines shape match) -- it has no separate check
for wave B briefly exceeding the start of the triangle (the defining trait
of a "running" triangle, itself a debated/rare sub-variant even in Prechter's
own text). Per explicit requirement not to rewrite corrective_waves.py, this
module does not add that check either: a running triangle will surface here
as CONTRACTING (its trendlines do still converge), not mislabeled as
something incompatible, just not distinguished from an ordinary contracting
triangle. Documented as a known limitation, not silently glossed over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .swing_identification import Swing
from .corrective_waves import Correction, CorrectionType, detect_triangle, find_combinations

# Below this quality, a candidate is dropped before it ever reaches the
# candidate pool -- ambiguous fits must never compete for (let alone win) a
# stretch of chart. Mirrors structure_classification.MIN_WINNER_CONFIDENCE's
# role, applied at candidate-generation time instead of at classification
# time since triangle/combination candidates bypass that classifier (see
# module docstring).
_MIN_QUALITY = 0.25

# Elliott's own convention for triangle legs (A-E) and combination
# connectors (W/X/Y/Z) is lowercase when used as top-level wave labels --
# mirrors the identical convention wave_analysis.py's
# ``_correction_boundary_labels`` already uses for the (separate) nested
# minor-degree hierarchy pass, kept consistent here rather than reinvented.
_TRIANGLE_LABELS = ["a", "b", "c", "d", "e"]


@dataclass
class CorrectiveCandidate:
    """Plain result type -- deliberately NOT wave_numbering.WaveLabel/
    _Candidate (see module docstring, "Why a separate module"). ``start_pos``/
    ``end_pos`` are positions in the SWING LIST (matching ``_Candidate.
    start_index``/``end_index``'s own convention), not bar indices."""
    correction: Correction
    boundary: List[Tuple[str, Swing]]   # (wave_label, swing) pairs, top-level only
    start_pos: int
    end_pos: int
    quality: float                       # 0..1, structural-fit confidence
    kind: str                            # "triangle" | "double_three" | "triple_three"


def _triangle_quality(corr: Correction) -> float:
    """0..1 structural-consistency read of a triangle candidate ``detect_triangle``
    already accepted -- NOT a second pass/fail gate (that already happened
    inside detect_triangle, unchanged). Rewards trendline convergence/
    divergence that's substantial relative to the structure's own price
    range; a triangle whose trendlines barely converge is a weak, easily-
    coincidental read even though it technically satisfies the shape check.
    """
    hc = abs(corr.metrics.get("high_convergence", 0.0))
    lc = abs(corr.metrics.get("low_convergence", 0.0))
    prices = [p.price for p in corr.pivots]
    own_range = (max(prices) - min(prices)) or 1e-9
    convergence = (hc + lc) / (2 * own_range)
    return round(min(1.0, max(0.15, convergence)), 3)


def _combination_quality(corr: Correction) -> float:
    """0..1 -- ``find_combinations`` already enforces the X-connector
    retracement lies within [x_min, x_max] (default 0.30-1.40) before a
    Correction is even returned; this only grades HOW CENTERED inside that
    band the read is (closer to the middle of the accepted range reads more
    like a genuine corrective connector than one sitting right at an edge),
    not a second acceptance test.
    """
    x = corr.metrics.get("x_retrace_of_W", 0.85)
    dist_from_center = abs(x - 0.85) / 0.55   # 0.55 = half of find_combinations' default 0.30-1.40 band
    base = round(max(0.2, 1.0 - dist_from_center), 3)
    if corr.type == CorrectionType.TRIPLE_THREE:
        base = round(base * 0.9, 3)   # one more unverified X-joint than a double three
    return base


def find_triangle_candidates(swings: List[Swing]) -> List[CorrectiveCandidate]:
    """Slide a 6-pivot window across ``swings`` and hand each one to
    ``corrective_waves.detect_triangle`` UNCHANGED (it requires exactly 6
    pivots per its own demo/docstring convention -- passing more would let
    its internal high/low-count check silently read pivots beyond the
    window it labels, a pre-existing quirk in that function this module
    works around by never triggering it, rather than editing that
    function). This function only scans for windows to offer it; the shape
    classification itself is entirely ``detect_triangle``'s.
    """
    out: List[CorrectiveCandidate] = []
    for i in range(len(swings) - 5):
        corr = detect_triangle(swings[i:i + 6])
        if corr is None:
            continue
        quality = _triangle_quality(corr)
        if quality < _MIN_QUALITY:
            continue
        boundary = list(zip(_TRIANGLE_LABELS, corr.pivots[1:6]))
        out.append(CorrectiveCandidate(
            correction=corr, boundary=boundary,
            start_pos=i, end_pos=i + 5,
            quality=quality, kind="triangle",
        ))
    return out


def find_complex_correction_candidates(swings: List[Swing]) -> List[CorrectiveCandidate]:
    """``corrective_waves.find_combinations`` already scans the whole swing
    list itself for 8-pivot (double three / WXY) and 12-pivot (triple three
    / WXYXZ) windows -- reused verbatim here, not reimplemented. This
    function only adapts each hit into a ``CorrectiveCandidate`` (recovering
    the swing-list start/end positions ``find_combinations`` doesn't itself
    return, and building the W/X/Y[/X/Z] boundary labels).
    """
    out: List[CorrectiveCandidate] = []
    for corr in find_combinations(swings):
        p = corr.pivots
        if corr.type == CorrectionType.DOUBLE_THREE:
            boundary = [("w", p[3]), ("x", p[4]), ("y", p[7])]
            kind = "double_three"
        elif corr.type == CorrectionType.TRIPLE_THREE:
            boundary = [("w", p[3]), ("x", p[4]), ("y", p[7]), ("x", p[8]), ("z", p[11])]
            kind = "triple_three"
        else:
            continue   # find_combinations only ever returns these two types, but never assume
        quality = _combination_quality(corr)
        if quality < _MIN_QUALITY:
            continue
        # Recover swing-list positions by identity, not by value -- pivots
        # are the SAME Swing objects find_combinations sliced out of
        # ``swings``, so identity search is exact and unambiguous even if
        # two swings share a price.
        start_pos = next(k for k, s in enumerate(swings) if s is p[0])
        end_pos = start_pos + len(p) - 1
        out.append(CorrectiveCandidate(
            correction=corr, boundary=boundary,
            start_pos=start_pos, end_pos=end_pos,
            quality=quality, kind=kind,
        ))
    return out


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    from .swing_identification import SwingType

    H, L = SwingType.HIGH, SwingType.LOW

    def _mk(idx: int, price: float, kind: SwingType) -> Swing:
        return Swing(idx, idx + 2, price, kind)

    print("=== triangle candidates ===")
    tri_swings = [_mk(0, 120, H), _mk(3, 100, L), _mk(6, 116, H),
                 _mk(9, 104, L), _mk(12, 112, H), _mk(15, 107, L)]
    for c in find_triangle_candidates(tri_swings):
        print(f"  {c.kind}: quality={c.quality:.2f} span=[{c.start_pos},{c.end_pos}] "
             f"boundary={[(l, s.price) for l, s in c.boundary]}")

    print("\n=== complex correction candidates (double three: W=expanded flat, X, Y=zigzag) ===")
    combo_swings = [_mk(0, 120, H), _mk(3, 104, L), _mk(6, 124, H), _mk(9, 100, L),
                   _mk(12, 114, H),
                   _mk(15, 98, L), _mk(18, 108, H), _mk(21, 90, L)]
    for c in find_complex_correction_candidates(combo_swings):
        print(f"  {c.kind}: quality={c.quality:.2f} span=[{c.start_pos},{c.end_pos}] "
             f"boundary={[(l, s.price) for l, s in c.boundary]}")

    print("\n=== ambiguous window -- expect no candidates (quality filtered or shape rejected) ===")
    noisy = [_mk(0, 100, L), _mk(3, 101, H), _mk(6, 99, L), _mk(9, 102, H),
            _mk(12, 98, L), _mk(15, 103, H)]
    print("  triangle candidates:", find_triangle_candidates(noisy))
