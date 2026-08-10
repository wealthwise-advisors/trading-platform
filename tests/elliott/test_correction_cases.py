"""Canonical Elliott correction test cases (Task 7, requirement 1).

Zigzag/Regular Flat/Expanded Flat/Running Flat fixtures are the SAME
pivot sequences corrective_waves.py's own __main__ demo already uses and
has been validated against since Tasks 2-3 -- reused, not re-derived, so
this suite is anchored to the one canonical example set rather than a
second, potentially-diverging one.

"Double Zigzag" / "Triple Zigzag" are not separate detector outputs --
per corrective_waves.py's own module docstring, they are the SPECIFIC
case of find_combinations' generic DOUBLE_THREE/TRIPLE_THREE where every
simple sub-part happens to independently classify as ZIGZAG. These tests
verify that specific case, not a new code path (no new Elliott feature).
"""
from conftest import mk_swing, assert_deterministic, H, L

from src.analysis.corrective_waves import classify_abc, find_combinations, CorrectionType


# --------------------------------------------------------------------------- #
# Simple corrections -- reused verbatim from corrective_waves.py's own demo
# --------------------------------------------------------------------------- #
def test_zigzag():
    pivots = [mk_swing(0, 120, H), mk_swing(1, 100, L), mk_swing(2, 115, H), mk_swing(3, 92, L)]
    corr = assert_deterministic(classify_abc, pivots)
    assert corr.type == CorrectionType.ZIGZAG
    b_retrace = corr.metrics["b_retrace_of_A"]
    assert b_retrace < 0.90, "hard boundary for ZIGZAG classification"


def test_regular_flat():
    pivots = [mk_swing(0, 120, H), mk_swing(1, 104, L), mk_swing(2, 119, H), mk_swing(3, 102, L)]
    corr = assert_deterministic(classify_abc, pivots)
    assert corr.type == CorrectionType.REGULAR_FLAT
    assert 0.90 <= corr.metrics["b_retrace_of_A"] <= 1.05


def test_expanded_flat():
    pivots = [mk_swing(0, 120, H), mk_swing(1, 104, L), mk_swing(2, 124, H), mk_swing(3, 100, L)]
    corr = assert_deterministic(classify_abc, pivots)
    assert corr.type == CorrectionType.EXPANDED_FLAT
    assert corr.metrics["b_retrace_of_A"] > 1.05
    assert corr.metrics["c_beyond_A"] > 0.05


def test_running_flat():
    pivots = [mk_swing(0, 120, H), mk_swing(1, 104, L), mk_swing(2, 124, H), mk_swing(3, 106, L)]
    corr = assert_deterministic(classify_abc, pivots)
    assert corr.type == CorrectionType.RUNNING_FLAT
    assert corr.metrics["b_retrace_of_A"] > 1.05
    assert corr.metrics["c_beyond_A"] <= 0.05


# --------------------------------------------------------------------------- #
# Double / triple zigzag -- a DOUBLE_THREE / TRIPLE_THREE combination
# whose W (and Y, and Z) sub-parts each independently resolve as ZIGZAG.
# --------------------------------------------------------------------------- #
def test_double_zigzag():
    swings = [
        mk_swing(0, 120, H), mk_swing(1, 100, L), mk_swing(2, 115, H), mk_swing(3, 90, L),   # W: zigzag
        mk_swing(4, 110, H), mk_swing(5, 88, L), mk_swing(6, 104, H), mk_swing(7, 80, L),    # X-end/Y: zigzag
    ]
    combos = assert_deterministic(find_combinations, swings)
    assert len(combos) == 1
    combo = combos[0]
    assert combo.type == CorrectionType.DOUBLE_THREE
    w, y = combo.subparts[0], combo.subparts[2]
    assert w.type == CorrectionType.ZIGZAG
    assert y.type == CorrectionType.ZIGZAG
    assert combo.subparts[1] == "X"


def test_triple_zigzag():
    swings = [
        mk_swing(0, 120, H), mk_swing(1, 100, L), mk_swing(2, 115, H), mk_swing(3, 90, L),   # W: zigzag
        mk_swing(4, 110, H), mk_swing(5, 88, L), mk_swing(6, 104, H), mk_swing(7, 80, L),    # Y: zigzag
        mk_swing(8, 98, H), mk_swing(9, 78, L), mk_swing(10, 92, H), mk_swing(11, 70, L),    # Z: zigzag
    ]
    # find_combinations SCANS every valid start position (documented,
    # correct behavior -- it also finds the Y+X+Z stretch starting at
    # position 4 as its own valid double three, etc; wave_analysis.py's own
    # _classify_corrective_leg already filters the same way for the same
    # reason). This test cares specifically about the FULL 12-pivot triple
    # three anchored at position 0.
    combos = assert_deterministic(find_combinations, swings)
    full = [c for c in combos if c.pivots[0] is swings[0] and len(c.pivots) == 12]
    assert len(full) == 1
    combo = full[0]
    assert combo.type == CorrectionType.TRIPLE_THREE
    assert len(combo.subparts) == 5
    w, y, z = combo.subparts[0], combo.subparts[2], combo.subparts[4]
    assert w.type == CorrectionType.ZIGZAG
    assert y.type == CorrectionType.ZIGZAG
    assert z.type == CorrectionType.ZIGZAG
    assert combo.subparts[1] == combo.subparts[3] == "X"
