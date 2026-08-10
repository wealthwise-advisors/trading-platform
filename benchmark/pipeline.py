"""Independent Industry Benchmark -- archetype dataset + comparison
pipeline (Task 9). Every price sequence here is the SAME kind of
hand-built, precisely-computed fixture already validated in Task 7's
regression suite (tests/elliott/test_*.py) -- reused because it's the
one thing in this whole benchmark that IS independently, objectively
sourced: the textbook DEFINITION of each pattern (see
reference_sources.access_notes for "frost_prechter"/"public_edu"), not a
specific historical chart's disputed interpretation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3

import numpy as np
import pandas as pd

from src.analysis.swing_identification import identify_swings
from src.analysis.indicators import calc_rsi
from src.analysis import wave_analysis as wa
from src.analysis import structure_classification as sc
from src.analysis import recursive_structure as rs
from src.analysis.wave_numbering import _generate_candidates, _select_best_counts

from benchmark.db import init_db, connect, new_id, now_iso

CHARTS_DIR = Path(__file__).parent / "charts"
CHARTS_DIR.mkdir(exist_ok=True)


def ohlc_from_pivots(pivot_prices: list, bars_per_leg: int = 8, noise: float = 0.12, seed: int = 3) -> pd.DataFrame:
    """Segments use endpoint=False (avoids the duplicate-flat-point fractal
    bug found and documented in Task 7's own test suite). A SEPARATE fix,
    specific to this benchmark: the final pivot needs trailing bars after
    it for the right-side fractal confirmation (left=2/right=2 needs 2
    CONFIRMING bars past a pivot) -- without them the very last intended
    pivot in every archetype is silently never detected at all. A few
    small bars continuing the same direction, well short of the next
    reversal, close that gap without introducing a new, different pivot."""
    rng = np.random.default_rng(seed)
    # Symmetric to the tail fix below: the FIRST intended pivot also needs
    # LEADING bars before it for the left-side fractal confirmation (left=2
    # needs 2 confirming bars BEFORE a pivot too) or it's silently never
    # detected either -- caught the same way, by checking identify_swings'
    # actual output against the intended pivot list rather than assuming
    # it matched. Sign must be the SAME as the first leg's own direction
    # (approach from the opposite side the leg is heading, so the origin
    # is a genuine local extremum, not a mid-trend point) -- gotten backwards
    # on the first attempt, caught by that same verification.
    head_step = (pivot_prices[1] - pivot_prices[0]) * 0.02
    closes = [pivot_prices[0] + head_step * k for k in range(3, 0, -1)]
    for a, b in zip(pivot_prices, pivot_prices[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivot_prices[-1])
    # Tail must pull BACK toward the prior pivot (opposite sign from the
    # final leg's own direction) so the final pivot stays the local
    # extreme and gets its right-side fractal confirmation -- a
    # continuation in the SAME direction (the bug caught while building
    # this benchmark) just pushes the true extreme further out, past
    # bars that still have no confirmation of their own.
    tail_step = (pivot_prices[-2] - pivot_prices[-1]) * 0.02
    closes.extend(pivot_prices[-1] + tail_step * k for k in range(1, 4))
    closes = np.asarray(closes, dtype=float) + rng.normal(0, noise, len(closes))
    high = closes + rng.uniform(0.03, 0.2, len(closes))
    low = closes - rng.uniform(0.03, 0.2, len(closes))
    open_ = np.roll(closes, 1)
    open_[0] = closes[0]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": closes})


# --------------------------------------------------------------------------- #
# Archetype dataset -- 13 cases. Pivots are the SAME numbers validated in
# tests/elliott/*.py against the real engine (Task 7); reused here as
# benchmark fixtures with an explicit expected_structure_type, not
# re-derived.
# --------------------------------------------------------------------------- #
ARCHETYPES = [
    {
        "name": "perfect_5_wave_impulse", "expected": "impulse",
        "pivots": [100, 140, 120, 220, 205, 226],
        "notes": "Frost & Prechter impulse definition: 5-3-5-3-5, no overlap, wave 3 not shortest. "
                "Every leg lands inside its documented Fibonacci band.",
    },
    {
        "name": "zigzag", "expected": "zigzag",
        "pivots": [120, 100, 115, 92],   # exact fixture validated in tests/elliott/test_correction_cases.py
        "notes": "b_retrace 0.75 (<0.90 zigzag threshold, StockCharts/CFI-documented definition).",
    },
    {
        "name": "regular_flat", "expected": "regular_flat",
        "pivots": [120, 104, 119, 102],
        "notes": "b_retrace ~0.94, within the documented 0.90-1.05 regular-flat band.",
    },
    {
        "name": "expanded_flat", "expected": "expanded_flat",
        "pivots": [120, 104, 124, 100],
        "notes": "b_retrace 1.25 (>1.05), c_beyond 0.25 (>0.05) -- documented expanded-flat definition.",
    },
    {
        "name": "running_flat", "expected": "running_flat",
        "pivots": [120, 104, 124, 106],
        "notes": "b_retrace 1.25 (>1.05), c_beyond -0.125 (<=0.05) -- documented running-flat definition.",
    },
    {
        "name": "contracting_triangle", "expected": "contracting_triangle",
        "pivots": [120, 100, 116, 104, 112, 107],   # exact fixture validated in tests/elliott/test_triangle_cases.py
        "notes": "Highs 120>116>112, lows 100<104<107 -- documented contracting-triangle definition.",
    },
    {
        "name": "expanding_triangle", "expected": "expanding_triangle",
        "pivots": [100, 101, 99, 102, 98, 103],
        "notes": "Highs ascending, lows descending -- documented expanding-triangle definition.",
    },
    {
        "name": "double_zigzag", "expected": "double_three",
        "pivots": [120, 100, 115, 90, 110, 88, 104, 80],   # exact fixture validated in tests/elliott/test_correction_cases.py
        "notes": "W and Y both classify_abc as zigzag -- 'double zigzag' is the specific case of a "
                "documented WXY combination where both legs are zigzags.",
    },
    {
        "name": "triple_zigzag", "expected": "triple_three",
        "pivots": [120, 100, 115, 90, 110, 88, 104, 80, 98, 78, 92, 70],   # exact fixture validated in Task 7
        "notes": "W, Y, and Z all classify_abc as zigzag -- documented WXYXZ combination case.",
    },
    {
        # Origin(100) -> wedge w1..w5 (120,110,126,118,130; wave4=118 overlaps
        # wave1=120) -> a small CONFIRMING pullback (122) so wave 5 remains a
        # genuine local extremum under real fractal detection (unlike Task 6/11's
        # hand-built Swing objects, which could skip straight past it) -> then
        # genuine continuation (155, 148, 170) well beyond wave 5.
        "name": "leading_diagonal", "expected": "leading_diagonal",
        "pivots": [100, 120, 110, 126, 118, 130, 122, 155, 148, 170],
        "notes": "Wedge with wave 4 overlapping wave 1 (118<120) PLUS genuine continuation after wave 5 -- "
                "documented leading-diagonal definition (Task 6 Improvement's forward-context redesign).",
    },
    {
        # Same wedge and confirming pullback, but a genuine SHARP reversal
        # (126 weak bounce, then 95 -- well below wave 4's own 118) after wave 5.
        "name": "ending_diagonal", "expected": "ending_diagonal",
        "pivots": [100, 120, 110, 126, 118, 130, 122, 126, 95, 100],
        "notes": "Same wedge, but genuine sharp reversal after wave 5 -- documented ending-diagonal definition.",
    },
    {
        "name": "wave2_invalidation", "expected": "invalid_impulse",
        "pivots": [100, 140, 95, 130, 90, 135, 88],
        "notes": "Wave 2 retraces 112.5% of wave 1 -- violates the universal hard rule (Wave 2 never "
                "retraces past the origin). Engine must NOT produce a completed impulse here.",
    },
    {
        "name": "wave4_overlap_invalidation", "expected": "invalid_impulse",
        "pivots": [100, 140, 120, 220, 135, 210, 138, 205, 132],
        "notes": "Wave 4 candidates repeatedly overlap wave 1's territory -- violates the universal hard "
                "rule (Wave 4 never overlaps Wave 1). Engine must degrade to a partial count, not force wave 4/5.",
    },
]


# --------------------------------------------------------------------------- #
# Task 9 Improvement, requirement 1: expand from 13 to 100+ cases. Every
# variant below is a DETERMINISTIC transform of one of the 13 textbook
# archetypes above -- not a new, independently-asserted pattern -- so the
# expected_structure_type carries forward with the same justification.
# Both transforms are genuine Elliott properties worth testing, not
# padding:
#   * scale: Elliott structures are explicitly SCALE-INVARIANT (the same
#     rules apply at every degree, from sub-minuette to supercycle) --
#     multiplying every pivot's distance from the origin by a constant
#     preserves every Fibonacci retracement ratio exactly.
#   * mirror: reflecting every pivot around the origin turns a bullish
#     structure into the equivalent bearish structure -- the theory is
#     explicitly direction-symmetric (impulses/corrections/diagonals are
#     each defined the same way up or down), so a correct engine must
#     detect both. This exercises the swing-kind (peak/trough) logic
#     under real fractal detection, not just relabeled test data.
# Compression (scale < 1) is deliberately NOT used: it would shrink the
# signal relative to the fixed noise floor in ohlc_from_pivots, risking
# noise-dominated fixtures that fail for a reason having nothing to do
# with the engine -- that would be a benchmark-construction confound, not
# a genuine robustness test.
# --------------------------------------------------------------------------- #
_VARIANT_SCALES = (1.0, 4.0)
_VARIANT_MIRRORS = (False, True)
_VARIANT_SEED_OFFSETS = (0, 1)


def scale_pivots(pivots: list, factor: float) -> list:
    origin = pivots[0]
    return [round(origin + (p - origin) * factor, 6) for p in pivots]


def mirror_pivots(pivots: list) -> list:
    origin = pivots[0]
    return [round(2 * origin - p, 6) for p in pivots]


def generate_synthetic_variants(archetypes: list = ARCHETYPES) -> list:
    variants = []
    for arch_index, arch in enumerate(archetypes):
        for scale in _VARIANT_SCALES:
            for mirror in _VARIANT_MIRRORS:
                for seed_offset in _VARIANT_SEED_OFFSETS:
                    pivots = scale_pivots(arch["pivots"], scale)
                    if mirror:
                        pivots = mirror_pivots(pivots)
                    # Stable, deterministic per-variant seed (list-position
                    # derived, same fix as Task 9's original hash() bug --
                    # never use hash() for this).
                    seed = arch_index * 1000 + int(scale * 10) + (500 if mirror else 0) + seed_offset
                    variants.append({
                        "name": f"{arch['name']}__x{scale:g}__{'mirror' if mirror else 'orig'}__s{seed_offset}",
                        "expected": arch["expected"],
                        "pivots": pivots,
                        "notes": f"{arch['notes']} [synthetic variant of '{arch['name']}': scale={scale:g}x, "
                                f"mirror={mirror}, seed_offset={seed_offset} -- ratios preserved by construction]",
                        "base_archetype": arch["name"],
                        "seed": seed,
                    })
    return variants


def _candidate_kind(waves: list) -> str:
    if waves == ["1", "2", "3", "4", "5"]:
        return "diagonal_or_impulse"
    if waves and waves[0] == "1":
        return "impulse"
    if waves and waves[0] == "w":
        return "combo"
    if waves and waves[0] == "a" and len(waves) == 5:
        return "triangle"
    return "other"


def direct_detection(swings, expected: str) -> dict:
    """Answers a DIFFERENT question than engine_structure_type: not "does
    the top-level continuous pipeline pick this as the chart's single
    dominant story" (which competes against everything else in the
    series, including things this benchmark's own fixtures incidentally
    create), but "does the SPECIFIC detector for this pattern, run
    directly on the archetype's own intended span, confirm it at all" --
    the fairer test of whether the underlying detection LOGIC agrees with
    the reference definition, isolated from top-level chart-wide
    competition. Reuses the exact same production functions, unmodified.
    """
    from src.analysis.corrective_waves import classify_abc, detect_triangle, find_combinations
    from src.analysis.diagonal_waves import _try_diagonal_shape
    from src.analysis.wave_numbering import _grow_count

    if expected in ("regular_flat", "expanded_flat", "running_flat", "zigzag") and len(swings) >= 4:
        corr = classify_abc(swings[:4])
        return {"detector": "classify_abc", "result": corr.type.value, "matches_expected": corr.type.value == expected}
    if expected in ("contracting_triangle", "expanding_triangle") and len(swings) >= 6:
        tri = detect_triangle(swings[:6])
        result = f"{tri.metrics['shape']}_triangle" if tri else None
        return {"detector": "detect_triangle", "result": result, "matches_expected": result == expected}
    if expected in ("double_three", "triple_three"):
        combos = [c for c in find_combinations(swings) if c.pivots[0] is swings[0]]
        full = max(combos, key=lambda c: len(c.pivots)) if combos else None
        result = full.type.value if full else None
        return {"detector": "find_combinations", "result": result, "matches_expected": result == expected}
    if expected in ("leading_diagonal", "ending_diagonal") and len(swings) >= 6:
        d = _try_diagonal_shape(swings, 1)
        result = f"{d.position}_diagonal" if d else None
        return {"detector": "_try_diagonal_shape", "result": result, "matches_expected": result == expected}
    if expected == "impulse" and len(swings) >= 3:
        result = _grow_count(swings, 1, None)
        found = result is not None and [w.wave for w in result[0]][:5] == ["1", "2", "3", "4", "5"]
        return {"detector": "_grow_count", "result": "impulse" if found else "partial_or_none", "matches_expected": found}
    if expected == "invalid_impulse" and len(swings) >= 3:
        result = _grow_count(swings, 1, None)
        completed = result is not None and "5" in [w.wave for w in result[0]]
        return {"detector": "_grow_count", "result": "illegally_completed" if completed else "correctly_rejected_or_partial",
               "matches_expected": not completed}
    return {"detector": None, "result": None, "matches_expected": None}


def run_engine_on_archetype(df: pd.DataFrame) -> dict:
    """Runs the REAL, unmodified engine and extracts the same fields
    validation/pipeline.py does for Task 8, plus a single dominant
    'engine_structure_type' classification for the primary-agreement check."""
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    rsi = calc_rsi(df["close"], 14) if len(df) > 20 else None
    wa_result = wa.analyze(df)

    token = sc.set_recursion_context(df)
    try:
        candidates, _ = _generate_candidates(swings, rsi)
        selected, alternates = _select_best_counts(candidates, len(swings))

        recursive_results = []
        for cand in selected:
            bar_start, bar_end = cand.labels[0].index, cand.labels[-1].index
            if bar_end > bar_start:
                rv = rs.verify_recursive_structure(df, bar_start, bar_end, sc._unified_recursive_detector, "unified")
                recursive_results.append({
                    "verified": rv.verified, "confidence": round(rv.confidence, 3),
                    "depth_reached": rv.depth_reached, "resolved_type": rv.resolved_type,
                })
    finally:
        sc.reset_recursion_context(token)

    # dominant structure = the single highest-scoring selected candidate
    # (the archetype fixtures are built so exactly one genuine structure
    # should span most/all of the series)
    dominant = max(selected, key=lambda c: c.score) if selected else None
    engine_structure_type = None
    if dominant is not None:
        waves = [w.wave for w in dominant.labels]
        kind = _candidate_kind(waves)
        if kind == "impulse":
            engine_structure_type = "impulse"
        elif kind == "diagonal_or_impulse":
            # look up which -- diagonal candidates ALSO use "1".."5" labels;
            # disambiguate via find_diagonal_candidates on this exact span
            from src.analysis.diagonal_waves import find_diagonal_candidates
            diag = {(c.start_pos, c.end_pos): c for c in find_diagonal_candidates(swings)}
            d = diag.get((dominant.start_index, dominant.end_index))
            if d is not None:
                engine_structure_type = f"{d.position}_diagonal" if d.position != "unknown" else "diagonal_unknown_position"
            else:
                engine_structure_type = "impulse"
        elif kind == "combo":
            from src.analysis.complex_corrections import find_complex_correction_candidates
            combos = {(c.start_pos, c.end_pos): c for c in find_complex_correction_candidates(swings)}
            c = combos.get((dominant.start_index, dominant.end_index))
            engine_structure_type = c.kind if c else "combo"
        elif kind == "triangle":
            from src.analysis.complex_corrections import find_triangle_candidates
            tris = {(c.start_pos, c.end_pos): c for c in find_triangle_candidates(swings)}
            t = tris.get((dominant.start_index, dominant.end_index))
            engine_structure_type = f"{t.correction.metrics['shape']}_triangle" if t else "triangle"
        else:
            engine_structure_type = "other"
    else:
        engine_structure_type = "no_structure_found"

    confidence = None
    if dominant is not None:
        try:
            origin_pos = min(dominant.start_index, len(swings) - 1)
            detail = sc.classify_structure_detailed(swings, origin_pos, dominant.labels[0].direction)
            confidence = round(detail.winner_confidence, 3)
        except Exception:
            pass

    return {
        "engine_primary_count": [
            {"wave": w.wave, "price": round(w.price, 4), "bar": w.index, "kind": w.swing.kind.value}
            for w in wa_result.wave_sequence
        ],
        "engine_alternate_counts": list(wa_result.alternates) + list(alternates),
        "engine_structure_type": engine_structure_type,
        "confidence": confidence,
        "rule_warnings": list(wa_result.warnings),
        "recursive_verification": recursive_results,
    }


def populate_synthetic(conn: sqlite3.Connection, cases: list = None, verbose: bool = True) -> int:
    """Populates case_category='synthetic_archetype' rows. `cases` defaults
    to the full 104-variant set (13 archetypes x 2 scales x 2 mirrors x 2
    seeds); pass the raw ARCHETYPES list to reproduce Task 9's original 13."""
    cases = cases if cases is not None else generate_synthetic_variants()
    n = 0
    for i, arch in enumerate(cases):
        # Stable, deterministic seed -- Python's built-in hash() is
        # randomized per-process (PYTHONHASHSEED) unless disabled, which
        # silently made Task 9's original benchmark non-reproducible
        # across runs. Each variant carries its own pre-computed stable
        # seed (see generate_synthetic_variants); plain archetypes (no
        # "seed" key) fall back to their stable list position.
        seed = arch.get("seed", i)
        df = ohlc_from_pivots(arch["pivots"], bars_per_leg=6, seed=seed)
        csv_path = CHARTS_DIR / f"{arch['name']}.csv"
        df.to_csv(csv_path, index=False)

        chart_id = new_id("bchart")
        conn.execute(
            "INSERT INTO benchmark_charts (chart_id, source_id, case_category, symbol, timeframe, date_range, degree, "
            "expected_structure_type, expected_primary_count_json, expected_alternate_counts_json, notes, price_csv_path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (chart_id, "frost_prechter", "synthetic_archetype", "SYNTHETIC", "N/A", "N/A", "primary",
            arch["expected"], "[]", "[]", arch["notes"], str(csv_path)),
        )

        result = run_engine_on_archetype(df)
        run_id = new_id("brun")
        conn.execute(
            "INSERT INTO benchmark_runs (run_id, chart_id, run_index, engine_primary_count_json, engine_alternate_counts_json, "
            "engine_structure_type, confidence, rule_warnings_json, recursive_verification_json, run_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, chart_id, 0, json.dumps(result["engine_primary_count"]), json.dumps(result["engine_alternate_counts"]),
            result["engine_structure_type"], result["confidence"], json.dumps(result["rule_warnings"]),
            json.dumps(result["recursive_verification"]), now_iso()),
        )
        n += 1
        if verbose:
            print(f"  {arch['name']:40} expected={arch['expected']:22} engine={result['engine_structure_type']:22} "
                 f"confidence={result['confidence']}")
    return n


if __name__ == "__main__":
    init_db()
    with connect() as conn:
        count = populate_synthetic(conn)
    print(f"\n{count} synthetic archetype benchmarks populated")
