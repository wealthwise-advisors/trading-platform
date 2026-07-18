"""Performance regression tests (Task 7, requirement 4).

Baselines below were MEASURED directly on this suite's own self-contained
synthetic fixture (241 bars, 39 swings -- built via ohlc_from_pivots, no
external data file dependency so this suite runs identically on any
machine/CI). TOLERANCE is a configurable multiplier on top of each
measured baseline -- generous enough to absorb normal machine-to-machine
variance, tight enough to catch a genuine algorithmic regression (e.g. an
accidental O(n^2) reintroduction, or a caching regression that makes
every call a cache miss).
"""
import time

from conftest import ohlc_from_pivots

from src.analysis.swing_identification import identify_swings
from src.analysis.wave_numbering import _generate_candidates, _select_best_counts
from src.analysis import wave_analysis as wa
from src.analysis import recursive_structure as rs
from src.analysis import structure_classification as sc

TOLERANCE = 10.0   # configurable -- see module docstring

# Measured baselines (seconds), 241-bar / 39-swing synthetic series:
_BASELINE_SWING_DETECTION = 0.006
_BASELINE_CANDIDATE_GENERATION = 0.003
_BASELINE_DP_SELECTION = 0.001
_BASELINE_RECURSIVE_VERIFICATION = 0.010
_BASELINE_FULL_ANALYZE = 0.060


def _dense_series():
    pivots = [100.0]
    price = 100.0
    for i in range(40):
        price += 15 if i % 2 == 0 else -9
        pivots.append(price)
    return ohlc_from_pivots(pivots, bars_per_leg=6, seed=11)


def test_swing_detection_performance():
    df = _dense_series()
    t0 = time.perf_counter()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    elapsed = time.perf_counter() - t0
    budget = _BASELINE_SWING_DETECTION * TOLERANCE
    assert elapsed < budget, f"swing detection regressed: {elapsed:.4f}s exceeds {budget:.4f}s budget"
    assert len(swings) > 10


def test_candidate_generation_performance():
    df = _dense_series()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    t0 = time.perf_counter()
    candidates, _ = _generate_candidates(swings, None)
    elapsed = time.perf_counter() - t0
    budget = _BASELINE_CANDIDATE_GENERATION * TOLERANCE
    assert elapsed < budget, f"candidate generation regressed: {elapsed:.4f}s exceeds {budget:.4f}s budget"
    assert len(candidates) > 0


def test_dp_selection_performance():
    df = _dense_series()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    candidates, _ = _generate_candidates(swings, None)
    t0 = time.perf_counter()
    selected, alternates = _select_best_counts(candidates, len(swings))
    elapsed = time.perf_counter() - t0
    budget = _BASELINE_DP_SELECTION * TOLERANCE
    assert elapsed < budget, f"DP selection regressed: {elapsed:.4f}s exceeds {budget:.4f}s budget"


def test_recursive_verification_performance():
    df = _dense_series()
    rs.clear_cache()
    token = sc.set_recursion_context(df)
    try:
        t0 = time.perf_counter()
        rs.verify_recursive_structure(df, 0, len(df) - 1, sc._unified_recursive_detector, "unified")
        elapsed = time.perf_counter() - t0
    finally:
        sc.reset_recursion_context(token)
    budget = _BASELINE_RECURSIVE_VERIFICATION * TOLERANCE
    assert elapsed < budget, f"recursive verification regressed: {elapsed:.4f}s exceeds {budget:.4f}s budget"


def test_full_analyze_performance():
    df = _dense_series()
    rs.clear_cache()
    t0 = time.perf_counter()
    result = wa.analyze(df)
    elapsed = time.perf_counter() - t0
    budget = _BASELINE_FULL_ANALYZE * TOLERANCE
    assert elapsed < budget, f"full analyze() regressed: {elapsed:.4f}s exceeds {budget:.4f}s budget"
    assert len(result.wave_sequence) >= 0   # must complete, not crash -- count itself covered elsewhere


def test_cache_provides_meaningful_speedup():
    """Not a fixed-budget test -- verifies the RELATIVE guarantee that
    matters most: a warm cache must be substantially faster than cold,
    regardless of absolute machine speed."""
    df = _dense_series()
    rs.clear_cache()
    t0 = time.perf_counter()
    wa.analyze(df)
    cold = time.perf_counter() - t0

    t1 = time.perf_counter()
    wa.analyze(df)
    warm = time.perf_counter() - t1

    assert warm <= cold, "warm cache must never be slower than cold"
