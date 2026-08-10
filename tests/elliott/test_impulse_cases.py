"""Canonical Elliott impulse test cases (Task 7, requirement 1).

Each case is a hand-built swing sequence with EXACT, precomputed Fibonacci
ratios (not approximated) so the expected outcome is a mathematical
consequence of wave_numbering.py's own documented rules
(WAVE2_RETRACE/WAVE3_EXTENSION/WAVE4_RETRACE/WAVE5_EXTENSION,
_w5_structural_ok's "wave 3 never shortest" rule), not a guess. Where a
case is EXPECTED to fail or degrade, the assertion checks the exact
documented degrade-to-partial-count behavior (wave_numbering.py's module
docstring), not an exception.
"""
from conftest import mk_swing, ohlc_from_pivots, assert_deterministic, H, L

from src.analysis.wave_numbering import (
    _grow_count, _score_candidate, _generate_candidates, _select_best_counts,
)
from src.analysis import structure_classification as sc


def _wave_prices(labels):
    return {w.wave: w.price for w in labels}


# --------------------------------------------------------------------------- #
# 1. Perfect 5-wave impulse -- every leg lands inside its Fibonacci band
# --------------------------------------------------------------------------- #
def test_perfect_5_wave_impulse():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 220, H), mk_swing(4, 205, L), mk_swing(5, 226, H)]

    result = assert_deterministic(_grow_count, swings, 1, None)
    assert result is not None, "a textbook-legal impulse must not be rejected"
    labels, next_i, warnings = result
    prices = _wave_prices(labels)

    # correct numbering
    assert [w.wave for w in labels] == ["1", "2", "3", "4", "5"]
    assert prices == {"1": 140, "2": 120, "3": 220, "4": 205, "5": 226}
    assert warnings == []

    # hard Elliott rules, verified directly from the ratios (not assumed)
    assert 0.0 < (140 - 120) / 40 < 1.0                       # wave 2 holds origin
    assert (220 - 140) / 40 > 0                                # wave 3 exceeds wave 1
    assert 205 > 140                                            # wave 4 does not overlap wave 1
    assert (226 - 205) > 0 and 226 > 220                       # wave 5 clears wave 4 AND wave 3
    len1, len3, len5 = 40, 220 - 120, 226 - 205
    assert not (len3 < len1 and len3 < len5)                   # wave 3 not the shortest

    # every sub-wave hit its Fibonacci band -> sub=1 (fib + pattern both confirmed)
    assert all(w.sub == 1 for w in labels if w.wave in ("2", "3", "4", "5"))

    # candidate scoring stability -- deterministic, finite, positive
    span = labels[-1].index - labels[0].index
    score = assert_deterministic(_score_candidate, labels, span * 4)
    assert score > 0

    # DP selection stability -- this exact count must be SELECTED, not just generated
    candidates, any_attempted = _generate_candidates(swings, None)
    assert any_attempted
    selected, _ = assert_deterministic(_select_best_counts, candidates, len(swings))
    assert any(prices == _wave_prices(c.labels) for c in selected)


# --------------------------------------------------------------------------- #
# 2. Extended Wave 3 -- ext3 = 4.0x (well past the 1.618-2.618 fib band) --
# legal (only the upper fib gate is a soft "sub" signal, not a hard rule)
# --------------------------------------------------------------------------- #
def test_extended_wave_3():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 300, H), mk_swing(4, 284, L), mk_swing(5, 306.4, H)]
    result = _grow_count(swings, 1, None)
    assert result is not None
    labels, _, _ = result
    assert [w.wave for w in labels] == ["1", "2", "3", "4", "5"]
    ext3 = (300 - 140) / 40
    assert ext3 > 2.618, "fixture must genuinely exceed the fib band to test the extension"
    w3 = next(w for w in labels if w.wave == "3")
    assert w3.sub == 2, "beyond the fib band -> pattern-only confidence, not fib+pattern"


# --------------------------------------------------------------------------- #
# 3. Extended Wave 5 -- ext5 = 2.5x (well past the 1.236-1.618 fib band)
# --------------------------------------------------------------------------- #
def test_extended_wave_5():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 220, H), mk_swing(4, 205, L), mk_swing(5, 242.5, H)]
    result = _grow_count(swings, 1, None)
    assert result is not None
    labels, _, _ = result
    assert [w.wave for w in labels] == ["1", "2", "3", "4", "5"]
    ext5 = (242.5 - 205) / (220 - 205)
    assert ext5 > 1.618, "fixture must genuinely exceed the fib band to test the extension"
    w5 = next(w for w in labels if w.wave == "5")
    assert w5.sub == 2


# --------------------------------------------------------------------------- #
# 4. Truncated 5th -- BOTH attempts at wave 5 fail to clear wave 3. This
# engine enforces NO truncation exception (documented, hard rule) -- the
# count must degrade to a partial 1-2-3-4, never force a completion.
# --------------------------------------------------------------------------- #
def test_truncated_5th_degrades_to_partial_count():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 220, H), mk_swing(4, 205, L),
             mk_swing(5, 215, H), mk_swing(6, 195, L), mk_swing(7, 218, H)]
    assert 215 < 220 and 218 < 220, "fixture must genuinely fail to clear wave 3"

    result = assert_deterministic(_grow_count, swings, 1, None)
    assert result is not None
    labels, next_i, _ = result
    assert [w.wave for w in labels] == ["1", "2", "3", "4"], (
        "a wave 5 that never clears wave 3 must NOT be labeled -- no truncation exception"
    )
    assert next_i == 5   # first unconsumed swing is the first failed wave-5 attempt


# --------------------------------------------------------------------------- #
# 5. Failed impulse -- wave 3 never exceeds wave 1 (hard rule) -> None
# --------------------------------------------------------------------------- #
def test_failed_impulse_wave3_never_exceeds_wave1():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 135, H), mk_swing(4, 115, L), mk_swing(5, 138, H)]
    assert 135 < 140 and 138 < 140, "fixture must genuinely fail to clear wave 1"
    result = assert_deterministic(_grow_count, swings, 1, None)
    assert result is None


# --------------------------------------------------------------------------- #
# 6. Wave 2 invalidation -- wave 2 retraces 100%+ of wave 1 -> None
# --------------------------------------------------------------------------- #
def test_wave2_invalidation_full_retrace():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 95, L)]
    retrace2 = (140 - 95) / (140 - 100)
    assert retrace2 >= 1.0, "fixture must genuinely retrace past the origin"
    result = assert_deterministic(_grow_count, swings, 1, None)
    assert result is None


# --------------------------------------------------------------------------- #
# 7. Wave 4 overlap invalidation -- both wave-4 attempts land inside wave
# 1's territory -> degrades to a partial 1-2-3, wave 4 never labeled.
# --------------------------------------------------------------------------- #
def test_wave4_overlap_degrades_to_partial_count():
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 220, H),
             mk_swing(4, 135, L), mk_swing(5, 210, H), mk_swing(6, 138, L)]
    assert 135 < 140 and 138 < 140, "fixture must genuinely overlap wave 1"

    result = assert_deterministic(_grow_count, swings, 1, None)
    assert result is not None
    labels, next_i, _ = result
    assert [w.wave for w in labels] == ["1", "2", "3"], (
        "a wave 4 that overlaps wave 1 must NOT be labeled"
    )
    assert next_i == 4


# --------------------------------------------------------------------------- #
# Recursive verification -- a dense enough real price series built around
# the perfect-impulse pivots should let the unified recursive detector
# resolve without crashing, and (when it verifies at all) report a
# plausible resolved_type -- not asserting a specific one, since that
# depends on re-detected finer swings, but it must never silently explode.
# --------------------------------------------------------------------------- #
def test_perfect_impulse_recursive_verification_runs_cleanly():
    pivots = [100, 140, 120, 220, 205, 226]
    df = ohlc_from_pivots(pivots, bars_per_leg=10)
    swings = [mk_swing(0, 100, L), mk_swing(1, 140, H), mk_swing(2, 120, L),
             mk_swing(3, 220, H), mk_swing(4, 205, L), mk_swing(5, 226, H)]

    token = sc.set_recursion_context(df)
    try:
        detail = assert_deterministic(
            sc.classify_structure_detailed, swings, 5, "up",
        )
    finally:
        sc.reset_recursion_context(token)
    assert detail.winner is not None
    assert 0.0 <= detail.winner_confidence <= 1.0
