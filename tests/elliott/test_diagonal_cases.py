"""Canonical Elliott diagonal test cases (Task 7, requirement 1).

Wedge fixture is the exact pivot sequence diagonal_waves.py's own
__main__ demo uses. Leading/ending follow-through fixtures use the SAME
calibrated thresholds Task 6 Improvement measured from real data
(_ENDING_REVERSAL_THRESHOLD=0.15, _LEADING_CONTINUATION_THRESHOLD=-0.05).
"""
from conftest import mk_swing, assert_deterministic, H, L

from src.analysis.diagonal_waves import find_diagonal_candidates, _try_diagonal_shape


# Shared wedge: legs 20 -> 16 -> 12 (motive), 10 -> 8 (corrective) --
# genuinely narrowing, wave 4 (118) overlaps wave 1 (120): 118 < 120.
_ORIGIN = [mk_swing(12, 100, L)]
_WEDGE = [mk_swing(15, 120, H), mk_swing(18, 110, L), mk_swing(21, 126, H),
         mk_swing(24, 118, L), mk_swing(27, 130, H)]


def _wedge_hard_rules_hold(swings):
    origin, w1, w2, w3, w4, w5 = swings[:6]
    assert w1.price > origin.price                              # wave 1 makes genuine progress
    retrace2 = (w1.price - w2.price) / (w1.price - origin.price)
    assert 0.0 < retrace2 < 1.0                                   # wave 2 holds the origin
    assert w3.price > w1.price                                    # wave 3 exceeds wave 1
    assert w4.price < w1.price, "THE diagonal-defining rule: wave 4 must overlap wave 1"
    assert w5.price > w4.price                                    # wave 5 clears wave 4


def test_leading_diagonal():
    following = [mk_swing(30, 138, H), mk_swing(33, 132, L), mk_swing(36, 150, H),
                mk_swing(39, 145, L), mk_swing(42, 165, H)]
    swings = _ORIGIN + _WEDGE + following
    candidates = assert_deterministic(find_diagonal_candidates, swings)
    assert len(candidates) == 1
    cand = candidates[0]
    _wedge_hard_rules_hold(cand.pivots)
    assert cand.shape == "contracting"
    assert cand.position == "leading"
    assert cand.direction == "up"
    assert 0.0 <= cand.quality <= 1.0


def test_ending_diagonal():
    following = [mk_swing(30, 118, L), mk_swing(33, 122, H), mk_swing(36, 100, L),
                mk_swing(39, 105, H), mk_swing(42, 85, L)]
    swings = _ORIGIN + _WEDGE + following
    candidates = assert_deterministic(find_diagonal_candidates, swings)
    assert len(candidates) == 1
    cand = candidates[0]
    _wedge_hard_rules_hold(cand.pivots)
    assert cand.shape == "contracting"
    assert cand.position == "ending"


def test_diagonal_position_unknown_without_following_data():
    """No bars exist yet after wave 5 (the realistic live-detection case)
    -> UNKNOWN_DIAGONAL, never a forced leading/ending guess (Task 6
    Improvement requirement 4)."""
    swings = _ORIGIN + _WEDGE
    candidates = assert_deterministic(find_diagonal_candidates, swings)
    assert len(candidates) == 1
    assert candidates[0].position == "unknown"


def test_invalid_diagonal_no_overlap_rejected():
    """A normal impulse shape (wave 4 does NOT overlap wave 1) must NOT be
    detected as a diagonal at all -- the two are mutually exclusive by
    construction (Task 6): the overlap check and its negation can never
    both pass on the same window."""
    clean_impulse = [mk_swing(0, 100, L), mk_swing(3, 120, H), mk_swing(6, 110, L),
                     mk_swing(9, 140, H), mk_swing(12, 125, L), mk_swing(15, 160, H)]
    assert clean_impulse[4].price > clean_impulse[1].price, "fixture must genuinely NOT overlap wave 1"
    result = assert_deterministic(_try_diagonal_shape, clean_impulse, 1)
    assert result is None
    assert assert_deterministic(find_diagonal_candidates, clean_impulse) == []


def test_invalid_diagonal_non_monotonic_wedge_rejected():
    """Wave 4 overlaps wave 1 (satisfies the ONE defining rule) but the
    motive legs don't monotonically narrow or widen (wave 3's own leg is
    BIGGER than wave 1's, a mid-sequence bulge) -- not a clean wedge, must
    be rejected on shape grounds even though the overlap rule alone is
    met."""
    bulging = [mk_swing(12, 106, L), mk_swing(15, 120, H), mk_swing(18, 109, L),
              mk_swing(21, 124, H), mk_swing(24, 115, L), mk_swing(27, 126, H)]
    leg_wave1 = 120 - 106     # origin -> wave 1
    leg_wave3 = 124 - 109     # wave 2 -> wave 3
    assert leg_wave3 > leg_wave1, "fixture must genuinely bulge (wave 3's leg bigger than wave 1's)"
    assert 115 < 120, "overlap rule must still hold, isolating the shape check as the sole rejection reason"
    result = assert_deterministic(_try_diagonal_shape, bulging, 1)
    assert result is None
