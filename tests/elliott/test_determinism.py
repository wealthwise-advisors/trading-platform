"""Deterministic-output regression tests (Task 7, requirement 5).

Running analyze() (and the lower-level pipeline stages it's built from)
multiple times on IDENTICAL data must always produce byte-identical wave
sequences -- no run-to-run drift from dict/set iteration order, cache
state leaking between calls, or hidden randomness.
"""
from conftest import ohlc_from_pivots, assert_deterministic

from src.analysis.swing_identification import identify_swings
from src.analysis.wave_numbering import _generate_candidates, _select_best_counts, label_wave_sequence
from src.analysis import wave_analysis as wa
from src.analysis import recursive_structure as rs
from src.analysis import structure_classification as sc


def _dense_series():
    pivots = [100.0]
    price = 100.0
    for i in range(40):
        price += 15 if i % 2 == 0 else -9
        pivots.append(price)
    return ohlc_from_pivots(pivots, bars_per_leg=6, seed=11)


def _wave_signature(wave_sequence):
    """A plain, hashable-equality snapshot of a wave sequence -- wave
    label, price (rounded to avoid float-formatting noise), and bar
    index for every point, in order."""
    return tuple((w.wave, round(w.price, 6), w.index) for w in wave_sequence)


def test_full_analyze_deterministic_across_repeated_runs():
    df = _dense_series()
    rs.clear_cache()

    def run():
        return _wave_signature(wa.analyze(df).wave_sequence)

    assert_deterministic(run, runs=5)


def test_full_analyze_deterministic_cold_vs_warm_cache():
    """The cache must be a pure optimization -- warm-cache output must be
    IDENTICAL to cold-cache output, never merely similar."""
    df = _dense_series()
    rs.clear_cache()
    cold = _wave_signature(wa.analyze(df).wave_sequence)
    warm = _wave_signature(wa.analyze(df).wave_sequence)   # cache now populated from the cold run
    assert cold == warm


def test_candidate_generation_deterministic():
    df = _dense_series()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)

    def run():
        candidates, any_attempted = _generate_candidates(swings, None)
        return tuple((c.start_index, c.end_index, c.score, tuple(w.wave for w in c.labels)) for c in candidates)

    assert_deterministic(run, runs=5)


def test_dp_selection_deterministic():
    df = _dense_series()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    candidates, _ = _generate_candidates(swings, None)

    def run():
        selected, alternates = _select_best_counts(candidates, len(swings))
        return tuple((c.start_index, c.end_index, c.score) for c in selected), tuple(alternates)

    assert_deterministic(run, runs=5)


def test_label_wave_sequence_deterministic():
    df = _dense_series()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)

    def run():
        labels, warnings, alternates = label_wave_sequence(swings, rsi=None)
        return _wave_signature(labels), tuple(warnings), tuple(alternates)

    assert_deterministic(run, runs=5)


def test_recursive_verification_deterministic_across_cache_states():
    df = _dense_series()

    def run():
        rs.clear_cache()   # force a fresh cold computation every call
        rv = rs.verify_recursive_structure(df, 0, len(df) - 1, sc._unified_recursive_detector, "unified")
        return (rv.verified, rv.confidence, rv.depth_reached, rv.resolved_type)

    assert_deterministic(run, runs=5)


def test_classify_structure_deterministic_with_and_without_recursion():
    df = _dense_series()
    swings = identify_swings(df, left=2, right=2, min_move=0.0)

    def run_no_recursion():
        d = sc.classify_structure_detailed(swings, len(swings) - 1, "up")
        return (d.winner.value, d.winner_confidence)

    assert_deterministic(run_no_recursion, runs=5)

    def run_with_recursion():
        token = sc.set_recursion_context(df)
        try:
            d = sc.classify_structure_detailed(swings, len(swings) - 1, "up")
        finally:
            sc.reset_recursion_context(token)
        return (d.winner.value, d.winner_confidence)

    assert_deterministic(run_with_recursion, runs=5)
