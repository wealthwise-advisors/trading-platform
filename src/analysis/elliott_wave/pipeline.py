"""
pipeline.py
===========

The one correct call order, and the only module that knows it.

  pivots -> RSI -> impulses -> diagonals -> corrections -> measurements
         -> validation

The ordering is not arbitrary and is not a preference:

  * impulses before diagonals   -- LD-01/ED-01 need an impulse host to exist.
  * impulses before corrections -- ZZ-02 needs waves A and C to already be
                                   classifiable as five-wave structures.
  * measurements last           -- ratios are recorded on completed structures
                                   and never gate anything (FR-4.1).

Keeping the order here, and nowhere else, means it can be tested as a single
fact rather than inferred from call sites.

Determinism (FR-6.1 / FR-6.2): no randomness, no wall-clock, no I/O anywhere
in this package. Wave ids derive from (scale, start index, end index, kind),
so repeated runs over identical input produce byte-identical output.
"""

from __future__ import annotations

import pandas as pd

from . import (combination, correction, diagonal, hierarchy, impulse,
               measurements, momentum, pivots, validation)
from .models import (
    ELLIOTT_WAVE_ENGINE_VERSION,
    AnalysisResult,
    EngineConfig,
    Wave,
)


def run_analysis(df: pd.DataFrame, config: EngineConfig | None = None) -> AnalysisResult:
    """Analyse an OHLCV frame end to end.

    Parameters
    ----------
    df : the canonical price_data frame from BacktestResults. Consumed
         read-only; never mutated, never re-fetched (FR-1a.2 / FR-1a.3).
    config : pivot ladder settings. Defaults are the D-13 values.
    """
    cfg = config or EngineConfig()
    result = AnalysisResult(
        engine_version=ELLIOTT_WAVE_ENGINE_VERSION,
        config={
            "theta_base": cfg.theta_base,
            "ratio": cfg.ratio,
            "scales": cfg.scales,
            "rsi_period": cfg.rsi_period,
            "max_combination_depth": cfg.max_combination_depth,
            "thresholds": cfg.thresholds(),
        },
    )

    if df is None or len(df) < 2:
        result.notes.append("Input has fewer than 2 bars; no analysis performed.")
        validation.summarize(result, [])
        return result

    # 1. pivots
    all_pivots = pivots.detect_pivots(df, cfg)
    by_scale = pivots.by_scale(all_pivots)
    result.pivots = all_pivots

    for k in range(1, cfg.scales + 1):
        n = len(by_scale.get(k, []))
        if n < 2:
            result.notes.append(
                f"Scale {k} produced {n} pivot(s) -- too few to form any structure. "
                "This scale contributed nothing."
            )

    # cross-scale containment: measured and reported, never assumed (FR-1d.4)
    containment = {}
    for k in sorted(by_scale):
        if k - 1 in by_scale:
            rate = hierarchy.containment_rate(by_scale[k], by_scale[k - 1])
            if rate is not None:
                containment[f"scale{k}_in_scale{k-1}"] = round(rate, 4)
    result.config["cross_scale_containment"] = containment

    # 2. RSI(13) for IMP-06
    rsi = momentum.rsi_series(df, cfg.rsi_period)

    # 3-5. structures, in dependency order
    spans = hierarchy.SpanIndex()
    imp_waves = impulse.classify_impulses(by_scale, rsi, spans)
    dia_waves, dia_notes = diagonal.classify_diagonals(by_scale, imp_waves, spans)
    result.notes.extend(dia_notes)
    cor_waves = correction.classify_corrections(by_scale, spans)
    # Combinations last among the classifiers: DT-03/TT-03 consume the
    # correctives registered immediately above.
    com_waves = combination.classify_combinations(
        by_scale, spans, cfg.max_combination_depth)

    waves: list[Wave] = imp_waves + dia_waves + cor_waves + com_waves

    # 6. guideline ratios -- recorded, never matched
    by_id = {w.id: w for w in waves}
    structures = [w for w in waves if w.structure_type is not None]
    measurements.record(structures, by_id)

    # stable ordering for byte-identical output across runs
    waves.sort(key=lambda w: (w.scale, w.start_pivot.index, w.end_pivot.index, w.id))
    result.waves = waves

    # 7. honest reporting of what was not evaluated
    validation.summarize(result, waves)
    return result
