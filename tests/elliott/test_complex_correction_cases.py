"""Canonical Elliott complex-correction test cases (Task 7, requirement 1):
WXY and WXYXZ with GENERIC (non-zigzag-only) sub-parts, complementing the
zigzag-specific double/triple zigzag cases in test_correction_cases.py.
Exercises complex_corrections.find_complex_correction_candidates -- the
actual wrapper wave_numbering._generate_candidates calls, not the raw
corrective_waves.find_combinations directly.
"""
from conftest import mk_swing, assert_deterministic, H, L

from src.analysis.corrective_waves import CorrectionType
from src.analysis.complex_corrections import find_complex_correction_candidates, _combination_quality


def test_wxy_mixed_types():
    """W = expanded flat, Y = zigzag -- a genuine WXY where the two simple
    corrections are DIFFERENT shapes, not the same one twice."""
    swings = [
        mk_swing(0, 120, H), mk_swing(1, 104, L), mk_swing(2, 124, H), mk_swing(3, 100, L),  # W: expanded flat
        mk_swing(4, 112, H), mk_swing(5, 92, L), mk_swing(6, 106, H), mk_swing(7, 85, L),    # X-end/Y: zigzag
    ]
    candidates = assert_deterministic(find_complex_correction_candidates, swings)
    full = [c for c in candidates if c.start_pos == 0 and c.end_pos == 7]
    assert len(full) == 1
    combo = full[0]
    assert combo.kind == "double_three"
    assert combo.correction.type == CorrectionType.DOUBLE_THREE
    assert combo.correction.metrics["W"] == "expanded_flat"
    assert combo.correction.metrics["Y"] == "zigzag"
    assert combo.boundary[0][0] == "w" and combo.boundary[1][0] == "x" and combo.boundary[2][0] == "y"

    quality = _combination_quality(combo.correction)
    assert 0.0 <= quality <= 1.0


def test_wxyxz_mixed_types():
    """W = expanded flat, Y = zigzag, Z = regular flat -- three genuinely
    different sub-shapes chained through two X connectors."""
    swings = [
        mk_swing(0, 120, H), mk_swing(1, 104, L), mk_swing(2, 124, H), mk_swing(3, 100, L),   # W: expanded flat
        mk_swing(4, 112, H), mk_swing(5, 92, L), mk_swing(6, 106, H), mk_swing(7, 85, L),     # Y: zigzag
        mk_swing(8, 97, H), mk_swing(9, 81, L), mk_swing(10, 96, H), mk_swing(11, 79, L),     # X2-end/Z: regular flat
    ]
    candidates = assert_deterministic(find_complex_correction_candidates, swings)
    full = [c for c in candidates if c.start_pos == 0 and c.end_pos == 11]
    assert len(full) == 1
    combo = full[0]
    assert combo.kind == "triple_three"
    assert combo.correction.type == CorrectionType.TRIPLE_THREE
    assert combo.correction.metrics["W"] == "expanded_flat"
    assert combo.correction.metrics["Y"] == "zigzag"
    assert combo.correction.metrics["Z"] == "regular_flat"
    labels = [b[0] for b in combo.boundary]
    assert labels == ["w", "x", "y", "x", "z"]
