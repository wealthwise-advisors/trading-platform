"""Expert Chart Validation Framework -- analysis pipeline (Task 8).

Fetches REAL market data, splits it into individual chart instances, and
runs the EXISTING, UNMODIFIED Elliott Wave engine on each one, extracting
every field the validation schema requires. Every number this module
writes to the database is a genuine, computed output of the production
engine -- nothing here alters Elliott algorithms or production code (this
entire package lives outside src/ and api/, importing from them only).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from typing import Optional

import pandas as pd

from src.analysis.swing_identification import identify_swings
from src.analysis.indicators import calc_rsi
from src.analysis import wave_analysis as wa
from src.analysis import structure_classification as sc
from src.analysis import recursive_structure as rs
from src.analysis.wave_numbering import _generate_candidates, _select_best_counts
from src.analysis.complex_corrections import find_triangle_candidates, find_complex_correction_candidates
from src.analysis.diagonal_waves import find_diagonal_candidates

from validation.db import insert_chart, insert_analysis

CHARTS_DIR = Path(__file__).parent / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

MARKETS = ["ES", "NQ", "SPY", "GC", "CL"]        # BTC/EURUSD: no genuine real data source available -- see README
UNAVAILABLE_MARKETS = ["BTC", "EURUSD"]
TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]


def _candidate_kind(waves: list) -> str:
    if waves == ["1", "2", "3", "4", "5"]:
        return "diagonal"
    if waves and waves[0] == "1":
        return "impulse"
    if waves and waves[0] == "w":
        return "combo"
    if waves and waves[0] == "a" and len(waves) == 5:
        return "triangle"
    return "other"


def _own_span(candidate) -> tuple:
    return candidate.labels[0].index, candidate.labels[-1].index


def analyze_chart(df: pd.DataFrame) -> dict:
    """Run the full, unmodified pipeline on one chart's worth of real bars
    and return every field the validation schema needs."""
    swings = identify_swings(df, left=2, right=2, min_move=0.0)
    rsi = calc_rsi(df["close"], 14) if len(df) > 20 and "close" in df.columns else None

    wa_result = wa.analyze(df)   # the SAME function the live API calls -- unmodified

    token = sc.set_recursion_context(df)
    try:
        candidates, _ = _generate_candidates(swings, rsi)
        selected, alternates = _select_best_counts(candidates, len(swings))

        tri_by_span = {(c.start_pos, c.end_pos): c for c in find_triangle_candidates(swings)}
        combo_by_span = {(c.start_pos, c.end_pos): c for c in find_complex_correction_candidates(swings)}
        diag_by_span = {(c.start_pos, c.end_pos): c for c in find_diagonal_candidates(swings)}

        impulse_q, corrective_q, triangle_q, diagonal_q = [], [], [], []
        confidences = []
        recursive_results = []
        rule_violations = []

        for cand in selected:
            waves = [w.wave for w in cand.labels]
            kind = _candidate_kind(waves)

            if kind == "impulse":
                core = [w for w in cand.labels if w.wave in ("2", "3", "4", "5")]
                if core:
                    impulse_q.append(sum(1 for w in core if w.sub == 1) / len(core))
                # hard-rule re-audit, recomputed independently from the final prices
                by_wave = {w.wave: w.price for w in cand.labels}
                if all(k in by_wave for k in ("1", "2")):
                    prices_before = [s for s in swings if s.index < cand.labels[0].index]
                    if prices_before:
                        origin_price = prices_before[-1].price
                        sign = 1.0 if by_wave["1"] > origin_price else -1.0
                        len1 = sign * (by_wave["1"] - origin_price)
                        if len1 > 0:
                            retrace2 = sign * (by_wave["1"] - by_wave["2"]) / len1
                            if not (0.0 < retrace2 < 1.0):
                                rule_violations.append(f"wave2 retrace {retrace2:.3f} outside (0,1)")
                        if "3" in by_wave and sign * (by_wave["3"] - by_wave["1"]) <= 0:
                            rule_violations.append("wave3 does not exceed wave1")
                        if "4" in by_wave and sign * (by_wave["4"] - by_wave["1"]) <= 0:
                            rule_violations.append("wave4 overlaps wave1 (impulse hard rule)")
                        if "5" in by_wave and "3" in by_wave and sign * (by_wave["5"] - by_wave["3"]) <= 0:
                            rule_violations.append("wave5 does not exceed wave3")
            elif kind == "combo":
                span = (cand.start_index, cand.end_index)
                c = combo_by_span.get(span)
                if c:
                    corrective_q.append(c.quality)
            elif kind == "triangle":
                span = (cand.start_index, cand.end_index)
                c = tri_by_span.get(span)
                if c:
                    triangle_q.append(c.quality)
            elif kind == "diagonal":
                span = (cand.start_index, cand.end_index)
                c = diag_by_span.get(span)
                if c:
                    diagonal_q.append(round(0.7 * c.quality + 0.3 * c.subdivision_bonus, 3))

            direction = cand.labels[0].direction
            try:
                origin_swing_pos = cand.start_index if cand.start_index < len(swings) else len(swings) - 1
                detail = sc.classify_structure_detailed(swings, origin_swing_pos, direction)
                confidences.append(round(detail.winner_confidence, 3))
            except Exception:
                pass

            bar_start, bar_end = _own_span(cand)
            if bar_end > bar_start:
                rv = rs.verify_recursive_structure(
                    df, bar_start, bar_end, sc._unified_recursive_detector, "unified",
                )
                recursive_results.append({
                    "kind": kind, "bar_span": [bar_start, bar_end],
                    "verified": rv.verified, "confidence": round(rv.confidence, 3),
                    "depth_reached": rv.depth_reached, "resolved_type": rv.resolved_type,
                })
    finally:
        sc.reset_recursion_context(token)

    def _avg(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "n_swings": wa_result.n_swings,
        "bias": wa_result.bias,
        "cycle_position": wa_result.cycle_position,
        "primary_count": [
            {"wave": w.wave, "price": round(w.price, 4), "bar": w.index, "kind": w.swing.kind.value}
            for w in wa_result.wave_sequence
        ],
        "alternates": list(wa_result.alternates) + list(alternates),
        "impulse_quality": _avg(impulse_q),
        "corrective_quality": _avg(corrective_q),
        "triangle_quality": _avg(triangle_q),
        "diagonal_quality": _avg(diagonal_q),
        "confidence": _avg(confidences),
        "recursive_verification": recursive_results,
        "rule_violations": rule_violations,
        "warnings": list(wa_result.warnings),
        "notes": list(wa_result.notes),
    }


def segment_series(df: pd.DataFrame, window_bars: int) -> list:
    """Cut a long real series into non-overlapping chart-sized windows --
    genuinely distinct chart instances, not pseudo-duplicated overlapping
    slices. Returns (start_bar, segment_df) so callers can recover which
    bars of the source series a chart came from."""
    segments = []
    for start in range(0, len(df) - window_bars + 1, window_bars):
        segments.append((start, df.iloc[start:start + window_bars].reset_index(drop=True)))
    return segments


def populate_market_timeframe(conn: sqlite3.Connection, market: str, timeframe: str,
                              df: pd.DataFrame, window_bars: int, data_source: str,
                              price_csv_path: Optional[str] = None) -> int:
    count = 0
    for start_bar, seg in segment_series(df, window_bars):
        if len(seg) < 30:
            continue
        chart_id = insert_chart(
            conn, market=market, timeframe=timeframe,
            start_date=str(seg["timestamp"].iloc[0]) if "timestamp" in seg.columns else str(start_bar),
            end_date=str(seg["timestamp"].iloc[-1]) if "timestamp" in seg.columns else str(start_bar + len(seg)),
            bar_count=len(seg),
            data_source=data_source, price_csv_path=None,   # set below, once chart_id is known
        )
        # Each chart gets its OWN small CSV -- price_csv_path must point at
        # the EXACT bars this analysis ran on, not the whole source series,
        # so the review gallery can re-render precisely what the engine saw.
        seg_path = CHARTS_DIR / f"{chart_id}.csv"
        seg.to_csv(seg_path, index=False)
        conn.execute("UPDATE charts SET price_csv_path = ? WHERE chart_id = ?", (str(seg_path), chart_id))
        try:
            result = analyze_chart(seg)
        except Exception as exc:   # a single bad segment must not abort the whole population run
            result = {
                "n_swings": 0, "bias": "error", "cycle_position": "error",
                "primary_count": [], "alternates": [],
                "impulse_quality": None, "corrective_quality": None,
                "triangle_quality": None, "diagonal_quality": None, "confidence": None,
                "recursive_verification": [], "rule_violations": [f"analysis exception: {exc}"],
                "warnings": [], "notes": [],
            }
        insert_analysis(
            conn, chart_id=chart_id, degree="primary",
            n_swings=result["n_swings"], bias=result["bias"], cycle_position=result["cycle_position"],
            primary_count=result["primary_count"], alternates=result["alternates"],
            impulse_quality=result["impulse_quality"], corrective_quality=result["corrective_quality"],
            triangle_quality=result["triangle_quality"], diagonal_quality=result["diagonal_quality"],
            confidence=result["confidence"], recursive_verification=result["recursive_verification"],
            rule_violations=result["rule_violations"], warnings=result["warnings"], notes=result["notes"],
        )
        count += 1
    return count
