"""Independent Industry Benchmark -- Tier 2: real market data, objective
regime classification, ROBUSTNESS testing (Task 9 Improvement, requirement
1's "multiple regimes/symbols/timeframes/bull/bear/sideways/high-low-vol"
and requirement 6's "reproducibility/deterministic/repeatability").

Explicitly does NOT produce wave-count "agreement" numbers: there is no
independent, sourced reference wave count for an arbitrary real-market
window (that's exactly what Task 9's honesty note already established --
MotiveWave/ELWAVE/ElliottWaveForecast are inaccessible). Mixing that into
the accuracy metrics would fabricate an implied reference that doesn't
exist. Kept in its own case_category ('real_market_regime') and its own
robustness statistics, per requirement 2's explicit demand to distinguish
real / educational / synthetic examples.

Source data: 369 real, Schwab-cached OHLCV charts across 5 symbols (ES,
NQ, SPY, GC, CL) x 5 timeframes (5m/15m/1h/4h/1d), already fetched and
verified as genuine (not synthetic) in Task 8 -- reused, not re-fetched.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3

import pandas as pd

from benchmark.db import connect as bconn, new_id, now_iso
from benchmark.pipeline import run_engine_on_archetype
from benchmark.regime_classification import (
    classify_trend, realized_vol, classify_volatility_group, classify_volatility,
)

VALIDATION_DB = Path(__file__).parent.parent / "validation" / "validation.db"


def load_real_charts() -> list[dict]:
    conn = sqlite3.connect(VALIDATION_DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM charts ORDER BY chart_id")]
    conn.close()
    return rows


def populate_real_regime(bench_conn: sqlite3.Connection, limit: int = None, verbose: bool = True) -> int:
    charts = load_real_charts()
    if limit:
        charts = charts[:limit]

    # Pass 1: realized vol per chart, grouped by (market, timeframe) --
    # volatility regime is only meaningful RELATIVE to same-instrument,
    # same-timeframe peers (see regime_classification.py).
    dfs, vols_by_group = {}, {}
    for c in charts:
        df = pd.read_csv(c["price_csv_path"])
        dfs[c["chart_id"]] = df
        key = f"{c['market']}|{c['timeframe']}"
        vols_by_group.setdefault(key, []).append(realized_vol(df))
    group_medians = classify_volatility_group(vols_by_group)

    n = 0
    for c in charts:
        df = dfs[c["chart_id"]]
        trend, trend_stats = classify_trend(df)
        vol = realized_vol(df)
        key = f"{c['market']}|{c['timeframe']}"
        vol_regime = classify_volatility(vol, group_medians[key])

        result = run_engine_on_archetype(df)

        chart_id = new_id("bchart")
        bench_conn.execute(
            "INSERT INTO benchmark_charts (chart_id, source_id, case_category, symbol, timeframe, date_range, "
            "degree, regime_trend, regime_volatility, regime_realized_return, regime_realized_vol_pct, "
            "expected_structure_type, expected_primary_count_json, expected_alternate_counts_json, notes, price_csv_path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (chart_id, "schwab_real_market", "real_market_regime", c["market"], c["timeframe"],
            f"{c['start_date']} to {c['end_date']}", "primary", trend, vol_regime,
            trend_stats["total_log_return"], vol, None, "[]", "[]",
            f"Real Schwab-cached data, {c['bar_count']} bars. Objectively classified: trend_z="
            f"{trend_stats['trend_z']}, per_bar_vol={vol:.6f} (group median for {key}={group_medians[key]:.6f}). "
            f"No independent reference wave count exists for this window -- used for robustness "
            f"measurement (determinism, hard-rule compliance), NOT accuracy comparison.",
            c["price_csv_path"]),
        )

        run_id = new_id("brun")
        bench_conn.execute(
            "INSERT INTO benchmark_runs (run_id, chart_id, run_index, engine_primary_count_json, "
            "engine_alternate_counts_json, engine_structure_type, confidence, rule_warnings_json, "
            "recursive_verification_json, rule_violations_json, run_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, chart_id, 0, json.dumps(result["engine_primary_count"]), json.dumps(result["engine_alternate_counts"]),
            result["engine_structure_type"], result["confidence"], json.dumps(result["rule_warnings"]),
            json.dumps(result["recursive_verification"]), json.dumps(result["rule_warnings"]), now_iso()),
        )
        n += 1
        if verbose and n % 50 == 0:
            print(f"  ... {n}/{len(charts)} real-market cases populated")
    return n


if __name__ == "__main__":
    with bconn() as conn:
        count = populate_real_regime(conn)
    print(f"\n{count} real-market regime benchmarks populated")
