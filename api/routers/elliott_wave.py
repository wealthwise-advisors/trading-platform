"""Elliott Wave / Fibonacci analysis endpoint. Wraps src/analysis/wave_analysis.py
(itself built on swing_identification / elliott_wave / corrective_waves / fibonacci)
around a backtest's own price data. Pure rule-based math -- no LLM, no external call.
"""

import math

import numpy as np
from fastapi import APIRouter, HTTPException

from src.analysis.wave_analysis import analyze_degrees, WaveAnalysis
from src.analysis.swing_identification import Swing, identify_swings, atr
from src.analysis.elliott_wave import ImpulseWave
from src.analysis.corrective_waves import Correction
from src.analysis.fibonacci import ClusterZone
from src.analysis.wave_numbering import WaveLabel
from api import store

router = APIRouter(prefix="/backtests", tags=["elliott-wave"])

# Same degree configs analyze_degrees() uses internally by default -- kept in
# sync here so the standalone "full swings list" (which wave_analysis.py's
# WaveAnalysis doesn't itself expose) matches exactly what each degree saw.
_DEGREES = [
    {"name": "primary", "left": 4, "right": 4, "mm_mult": 2.0},
    {"name": "minor", "left": 2, "right": 2, "mm_mult": 1.0},
]


def _safe(x):
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def _swing_to_dict(s: Swing, timestamps) -> dict:
    return {
        "t": timestamps[s.index].isoformat(),
        "price": _safe(round(s.price, 4)),
        "kind": s.kind.value,
        "label": s.label.value if s.label else None,
    }


def _impulse_to_dict(w: ImpulseWave, timestamps) -> dict:
    return {
        "direction": w.direction,
        "valid": w.valid,
        "rules": w.rules,
        "fib_score": _safe(w.fib_score),
        "truncated_fifth": w.truncated_fifth,
        "pivots": [_swing_to_dict(p, timestamps) for p in w.pivots],
    }


def _correction_to_dict(c: Correction, timestamps) -> dict:
    return {
        "type": c.type.value,
        "direction": c.direction,
        "metrics": {k: _safe(v) for k, v in c.metrics.items()},
        "pivots": [_swing_to_dict(p, timestamps) for p in c.pivots],
    }


def _wave_label_to_dict(w: WaveLabel, timestamps) -> dict:
    return {
        "t": timestamps[w.index].isoformat(),
        "price": _safe(round(w.price, 4)),
        "kind": w.swing.kind.value,
        "wave": w.wave,
        "sub": w.sub,
        "direction": w.direction,
    }


def _zone_to_dict(z: ClusterZone) -> dict:
    return {
        "center": _safe(z.center), "low": _safe(z.low), "high": _safe(z.high),
        "strength": z.strength,
        "members": [{"price": _safe(p), "source": src} for p, src in z.members],
    }


def _analysis_to_dict(a: WaveAnalysis, timestamps, swings: list) -> dict:
    return {
        "degree": a.degree,
        "trend": a.trend,
        "n_swings": a.n_swings,
        "swings": [_swing_to_dict(s, timestamps) for s in swings],
        "impulse": _impulse_to_dict(a.impulse, timestamps) if a.impulse else None,
        "impulse_fib": a.impulse_fib,
        "correction": _correction_to_dict(a.correction, timestamps) if a.correction else None,
        "correction_fib": a.correction_fib,
        "cycle_position": a.cycle_position,
        "bias": a.bias,
        "invalidation": _safe(a.invalidation),
        "target_zones": [_zone_to_dict(z) for z in a.target_zones],
        "alternates": a.alternates,
        "notes": a.notes,
        "warnings": a.warnings,
        "wave_sequence": [_wave_label_to_dict(w, timestamps) for w in a.wave_sequence],
    }


@router.get("/{backtest_id}/elliott-wave")
def get_elliott_wave(backtest_id: str):
    stored = store.get(backtest_id)
    if stored is None:
        raise HTTPException(404, f"Backtest {backtest_id!r} not found — it may have expired.")
    df = stored.results.price_data
    if df.empty:
        raise HTTPException(400, "No price data available for this backtest.")

    degrees = analyze_degrees(df)
    timestamps = df.index

    med = float(np.nanmedian(atr(df["high"], df["low"], df["close"], 14)))
    swings_by_degree = {
        d["name"]: identify_swings(df, left=d["left"], right=d["right"], min_move=d["mm_mult"] * med)
        for d in _DEGREES
    }

    return {
        name: _analysis_to_dict(a, timestamps, swings_by_degree.get(name, []))
        for name, a in degrees.items()
    }
