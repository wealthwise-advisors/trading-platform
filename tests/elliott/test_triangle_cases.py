"""Canonical Elliott triangle test cases (Task 7, requirement 1).

Contracting/expanding fixtures reuse the exact pivot sequences already
validated in corrective_waves.py's own __main__ demo and complex_
corrections.py's Task 5 test case.

"Running" triangle: detect_triangle has never distinguished a running
triangle from a contracting one by a dedicated rule (documented in
diagonal_waves.py's module docstring precedent for the analogous diagonal
case, and in complex_corrections.py's own docstring for this module).
Verified here empirically rather than assumed: a genuine running triangle
(wave B exceeds the triangle's own starting extreme) breaks monotonicity
on BOTH the ascending and descending checks simultaneously, so
detect_triangle returns None outright -- it does NOT silently mislabel a
running triangle as contracting, as an earlier docstring speculated. This
test locks in the VERIFIED behavior (rejection, not mislabeling) as a
regression guard.
"""
from conftest import mk_swing, assert_deterministic, H, L

from src.analysis.corrective_waves import detect_triangle
from src.analysis.complex_corrections import find_triangle_candidates, _triangle_quality


def test_contracting_triangle():
    pivots = [mk_swing(0, 120, H), mk_swing(1, 100, L), mk_swing(2, 116, H),
             mk_swing(3, 104, L), mk_swing(4, 112, H), mk_swing(5, 107, L)]
    corr = assert_deterministic(detect_triangle, pivots)
    assert corr is not None
    assert corr.metrics["shape"] == "contracting"
    highs = [pivots[0].price, pivots[2].price, pivots[4].price]
    lows = [pivots[1].price, pivots[3].price, pivots[5].price]
    assert highs[0] > highs[1] > highs[2], "highs must genuinely converge downward"
    assert lows[0] < lows[1] < lows[2], "lows must genuinely converge upward"

    quality = _triangle_quality(corr)
    assert 0.0 <= quality <= 1.0


def test_expanding_triangle():
    pivots = [mk_swing(0, 100, L), mk_swing(1, 101, H), mk_swing(2, 99, L),
             mk_swing(3, 102, H), mk_swing(4, 98, L), mk_swing(5, 103, H)]
    corr = assert_deterministic(detect_triangle, pivots)
    assert corr is not None
    assert corr.metrics["shape"] == "expanding"
    lows = [pivots[0].price, pivots[2].price, pivots[4].price]
    highs = [pivots[1].price, pivots[3].price, pivots[5].price]
    assert highs[0] < highs[1] < highs[2], "highs must genuinely diverge upward"
    assert lows[0] > lows[1] > lows[2], "lows must genuinely diverge downward"


def test_running_triangle_not_supported_rejected_not_mislabeled():
    """Documents VERIFIED (not assumed) behavior: detect_triangle has no
    dedicated running-triangle rule. A genuine running shape (B exceeds
    the triangle's own starting extreme) breaks monotonicity on BOTH the
    contracting and expanding checks at once, so the shape is REJECTED
    (None), never silently classified as something it isn't. This is the
    honest, current behavior -- not a bug to fix in this task (per
    explicit scope: no new Elliott functionality)."""
    running = [mk_swing(0, 120, H), mk_swing(1, 95, L), mk_swing(2, 125, H),
              mk_swing(3, 100, L), mk_swing(4, 115, H), mk_swing(5, 105, L)]
    assert running[2].price > running[0].price, "fixture must genuinely overshoot the start (the defining running trait)"
    corr = assert_deterministic(detect_triangle, running)
    assert corr is None


def test_triangle_candidate_generation_matches_detect_triangle():
    """Cross-check: complex_corrections.find_triangle_candidates (used by
    the real candidate-generation pipeline) must agree with detect_triangle
    (the underlying detector it reuses, unmodified) on the same shape."""
    swings = [mk_swing(0, 120, H), mk_swing(1, 100, L), mk_swing(2, 116, H),
             mk_swing(3, 104, L), mk_swing(4, 112, H), mk_swing(5, 107, L)]
    candidates = assert_deterministic(find_triangle_candidates, swings)
    assert len(candidates) == 1
    assert candidates[0].kind == "triangle"
    assert candidates[0].correction.metrics["shape"] == "contracting"
    assert candidates[0].start_pos == 0
    assert candidates[0].end_pos == 5
