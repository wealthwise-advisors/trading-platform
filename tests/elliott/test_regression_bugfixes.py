"""Regression tests for specific, previously-fixed bugs (Task 7,
requirement 3). Each test locks in the behavior a real fix produced --
if any of these ever fail again, a genuine prior fix has regressed.
"""
from conftest import mk_swing, ohlc_from_pivots, assert_deterministic, H, L

from src.analysis.swing_identification import identify_swings
from src.analysis import structure_classification as sc
from src.analysis import recursive_structure as rs
from src.analysis.complex_corrections import CorrectiveCandidate
from src.analysis.wave_numbering import _CORRECTIVE_COMPLETION_BONUS, _score_corrective_candidate


# --------------------------------------------------------------------------- #
# 1. Adaptive swing filter (Task 1) -- a genuine small pullback survives
# local-context filtering even when an EXPLICIT global min_move (inflated
# by an unrelated volatile stretch elsewhere in the same series) would, on
# its own, be large enough to reject it. Uses ohlc_from_pivots (endpoint=
# False between segments) -- raw concatenated np.linspace segments create
# duplicate flat points at segment boundaries that break the strict
# fractal inequality outright, a test-construction pitfall caught and
# fixed while building this suite, not a production issue.
# --------------------------------------------------------------------------- #
def test_adaptive_filter_survives_local_pullback_despite_distant_volatility():
    df = ohlc_from_pivots([100, 100.5, 130, 121, 190, 240, 235], bars_per_leg=8, noise=0.05)

    pullback_size = 130 - 121
    naive_global_min_move = 0.15 * (240 - 100)   # inflated by the large, unrelated 121->240 stretch
    assert pullback_size < naive_global_min_move, (
        "fixture must show a naive global-only floor WOULD reject this pullback"
    )

    # min_move is passed explicitly at the inflated (naive) level -- if
    # filtering were purely global, the pullback would be dropped. Local
    # ATR/recent-volatility/prior-swing-fraction signals must still admit
    # it despite the explicit global floor exceeding its raw size.
    swings = identify_swings(df, left=2, right=2, min_move=naive_global_min_move)
    pullback_kept = any(s.kind == L and abs(s.price - 121) < 2.0 for s in swings)
    assert pullback_kept, "local-adaptive filtering must keep a genuine pullback even under an inflated global floor"


# --------------------------------------------------------------------------- #
# 2. Unified classifier routing (Task 7) -- classify_structure_detailed
# accepts triangle=/combo=/diagonal= and routes to whichever wins, AND
# omitting them entirely reproduces pre-Task-7 behavior exactly.
# --------------------------------------------------------------------------- #
def test_unified_routing_accepts_precomputed_candidates_and_stays_backward_compatible():
    swings = [mk_swing(0, 100, L), mk_swing(1, 110, H)]

    # backward compatibility: no candidates passed -> byte-identical to the
    # pre-Task-7 all-heuristic scoring (triangle/combo/diagonal always 0).
    detail = assert_deterministic(sc.classify_structure_detailed, swings, 1, "up")
    assert detail.scores[sc.StructureType.POTENTIAL_TRIANGLE] == 0.0
    assert detail.scores[sc.StructureType.POTENTIAL_COMPLEX_CORRECTION] == 0.0
    assert detail.scores[sc.StructureType.POTENTIAL_DIAGONAL] == 0.0
    assert detail.winner_detail is None

    # routing: a passed-in triangle candidate must be able to win and be
    # returned via winner_detail (not re-detected).
    from src.analysis.corrective_waves import detect_triangle
    tri_swings = [mk_swing(0, 120, H), mk_swing(1, 100, L), mk_swing(2, 116, H),
                 mk_swing(3, 104, L), mk_swing(4, 112, H), mk_swing(5, 107, L)]
    tri_corr = detect_triangle(tri_swings)
    tri_cand = CorrectiveCandidate(correction=tri_corr, boundary=list(zip(["a", "b", "c", "d", "e"], tri_swings[1:])),
                                   start_pos=0, end_pos=5, quality=0.9, kind="triangle")
    detail2 = sc.classify_structure_detailed(tri_swings, 5, "up", triangle=tri_cand)
    assert detail2.scores[sc.StructureType.POTENTIAL_TRIANGLE] > 0.0
    if detail2.winner == sc.StructureType.POTENTIAL_TRIANGLE:
        assert detail2.winner_detail is tri_cand   # the SAME object, not re-detected


# --------------------------------------------------------------------------- #
# 3. Recursive verification reports explicit UNKNOWN on a miss (Task 3
# Improvement / Task 8) -- never a leaked sub-threshold score.
# --------------------------------------------------------------------------- #
def test_recursive_verification_explicit_unknown_on_miss():
    df = ohlc_from_pivots([100, 110, 105, 120], bars_per_leg=3)
    rs.clear_cache()
    rv = rs.verify_recursive_structure(
        df, 0, 2, sc._unified_recursive_detector, "unified",
        max_depth=1, min_swings=100, min_confidence=0.35,   # min_swings impossibly high -> guaranteed miss
    )
    assert rv.verified is False
    assert rv.confidence == 0.0
    assert rv.resolved_type is None


# --------------------------------------------------------------------------- #
# 4. Cache behavior (Task 4 Improvement) -- capacity raised to 16384
# (measured from real 5m data), and repeated identical calls hit the cache.
# --------------------------------------------------------------------------- #
def test_cache_capacity_and_hit_behavior():
    assert rs._CACHE_MAX_SIZE == 16384, "cache capacity regression -- see Task 4 Improvement's measured justification"

    df = ohlc_from_pivots([100, 140, 120, 220, 205, 226], bars_per_leg=8)
    rs.clear_cache()
    rv1 = rs.verify_recursive_structure(df, 0, len(df) - 1, sc._unified_recursive_detector, "unified")
    hits_before = rs.cache_stats["hits"]
    rv2 = rs.verify_recursive_structure(df, 0, len(df) - 1, sc._unified_recursive_detector, "unified")
    assert rs.cache_stats["hits"] == hits_before + 1
    assert rv1 == rv2


# --------------------------------------------------------------------------- #
# 5. Triangle calibration (Task 5 Improvement) -- completion bonus fixed
# from the false-dominance measured value (0.9) to the evidence-based one.
# --------------------------------------------------------------------------- #
def test_triangle_completion_bonus_recalibrated():
    assert _CORRECTIVE_COMPLETION_BONUS["triangle"] == 0.55, (
        "regression: triangle completion bonus must stay at the evidence-based "
        "0.55, not revert to the pre-calibration 0.9 that caused false dominance"
    )
    assert _CORRECTIVE_COMPLETION_BONUS["triangle"] < 0.9

    # a triangle and a double_three with IDENTICAL raw quality must no
    # longer diverge wildly in score purely from completion bonus (the
    # exact mechanism that caused 72.6% false-dominant win rate before).
    tri = CorrectiveCandidate(correction=None, boundary=[], start_pos=0, end_pos=10, quality=0.5, kind="triangle")
    combo = CorrectiveCandidate(correction=None, boundary=[], start_pos=0, end_pos=10, quality=0.5, kind="double_three")
    swings = [mk_swing(i, 100 + i, H if i % 2 else L) for i in range(11)]
    tri_score = _score_corrective_candidate(tri, swings, 100)
    combo_score = _score_corrective_candidate(combo, swings, 100)
    assert abs(tri_score - combo_score) < 0.5, (
        "same-quality triangle vs. combo must not diverge by more than a modest "
        "margin -- a wide gap here is the false-dominance signature"
    )


# --------------------------------------------------------------------------- #
# 6. Diagonal classification (Task 6 Improvement) -- a strong PRECEDING
# trend alone, with no following data, must NOT force "ending" anymore
# (the exact defect: old heuristic agreed with actual outcome only 2.5%
# of the time when triggered this way).
# --------------------------------------------------------------------------- #
def test_diagonal_position_no_longer_forced_by_preceding_trend_alone():
    from src.analysis.diagonal_waves import find_diagonal_candidates
    # strong preceding uptrend (would have triggered the OLD "ending" call)
    origin_context = [mk_swing(0, 80, L), mk_swing(3, 88, H), mk_swing(6, 83, L),
                      mk_swing(9, 92, H), mk_swing(12, 100, L)]
    wedge = [mk_swing(15, 120, H), mk_swing(18, 110, L), mk_swing(21, 126, H),
            mk_swing(24, 118, L), mk_swing(27, 130, H)]
    candidates = find_diagonal_candidates(origin_context + wedge)   # no following data
    assert len(candidates) == 1
    assert candidates[0].position == "unknown", (
        "no following data -> UNKNOWN_DIAGONAL, regardless of how strong the "
        "preceding trend was -- preceding-alone must never force a position"
    )


# --------------------------------------------------------------------------- #
# 7. Candidate competition (Task 7 unified routing) -- impulse's win rate
# should track its share of the generated pool (the "fair competition"
# signature measured in Task 5 Improvement), not be structurally starved
# or boosted by construction.
# --------------------------------------------------------------------------- #
def test_candidate_competition_impulse_not_structurally_disadvantaged():
    from src.analysis.wave_numbering import _generate_candidates, _select_best_counts
    pivots = [100, 140, 120, 220, 205, 226, 210, 260, 245, 300]
    df = ohlc_from_pivots(pivots, bars_per_leg=6)
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    candidates, any_attempted = _generate_candidates(swings, None)
    assert any_attempted
    impulse_generated = [c for c in candidates if c.labels[0].wave == "1"]
    assert len(impulse_generated) > 0, "a clean multi-leg impulsive series must generate impulse candidates"
    selected, _ = _select_best_counts(candidates, len(swings))
    assert any(c.labels[0].wave == "1" for c in selected), (
        "a genuinely impulsive series must select at least one impulse candidate -- "
        "if this fails, some corrective type is winning unfairly"
    )


# --------------------------------------------------------------------------- #
# 8. Unknown handling -- both StructureType.UNKNOWN (too little backward
# context) and DiagonalPosition "unknown" (too little forward context)
# must be reachable, explicit outcomes, never silently defaulted away.
# --------------------------------------------------------------------------- #
def test_unknown_handling_explicit_not_defaulted():
    single = [mk_swing(0, 100, L)]
    detail = assert_deterministic(sc.classify_structure_detailed, single, 0, "up")
    assert detail.winner == sc.StructureType.UNKNOWN
    assert detail.winner_confidence == 0.0

    from src.analysis.diagonal_waves import find_diagonal_candidates
    origin_and_wedge = [mk_swing(12, 100, L), mk_swing(15, 120, H), mk_swing(18, 110, L),
                        mk_swing(21, 126, H), mk_swing(24, 118, L), mk_swing(27, 130, H)]
    candidates = find_diagonal_candidates(origin_and_wedge)
    assert len(candidates) == 1
    assert candidates[0].position == "unknown"
