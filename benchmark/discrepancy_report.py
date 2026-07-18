"""Independent Industry Benchmark -- automatic discrepancy report (Task 9,
requirement 6). For every disagreement: reference count, engine count,
rule differences, confidence, a REAL rendered chart (not a placeholder),
and the recommendation + basis already computed in compare.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3

import pandas as pd

from benchmark.db import connect, fetch_all

_PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Elliott Wave Benchmark -- Discrepancy Report</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0; background: #f9f9f7; color: #0b0b0b; }}
.wrap {{ max-width: 1000px; margin: 0 auto; padding: 24px; }}
h1 {{ font-size: 20px; }}
.case {{ background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10); border-radius: 10px; padding: 16px; margin-bottom: 20px; }}
.case h2 {{ font-size: 15px; margin: 0 0 8px; }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 8px; }}
.badge.correct {{ background: #0ca30c22; color: #006300; }}
.badge.ambiguous {{ background: #fab21922; color: #7a5200; }}
.badge.refcorrect {{ background: #2a78d622; color: #184f95; }}
.badge.unverified {{ background: #89878122; color: #52514e; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 10px 0; font-size: 13px; }}
.plot {{ height: 240px; }}
.basis {{ font-size: 13px; color: #52514e; margin-top: 8px; border-left: 3px solid #e1e0d9; padding-left: 10px; }}
</style>
</head><body><div class="wrap">
<h1>Elliott Wave Benchmark -- Discrepancy Report</h1>
<p style="color:#52514e; font-size:13px;">Every case where the engine's top-level structure did not match the
archetype's documented definition. Each includes a real rendered chart (not a placeholder) and the same
evidence-grounded recommendation basis stored in benchmark_comparisons.</p>
{cases}
</div></body></html>
"""

_CASE_TEMPLATE = """
<div class="case">
  <h2>{name} <span class="badge {badge_class}">{recommendation}</span></h2>
  <div class="grid2">
    <div><b>Reference (expected):</b> {expected}</div>
    <div><b>Engine (top-level):</b> {engine_type}</div>
    <div><b>Confidence:</b> {confidence}</div>
    <div><b>Rule differences:</b> {rule_differences}</div>
  </div>
  <div id="plot-{idx}" class="plot"></div>
  <div class="basis"><b>Recommendation basis:</b> {basis}</div>
</div>
<script>
Plotly.newPlot('plot-{idx}', [{{
  type: 'candlestick', x: {bars_x}, open: {bars_open}, high: {bars_high}, low: {bars_low}, close: {bars_close},
}}], {{height: 240, margin: {{t:10,r:10,b:30,l:40}}, xaxis: {{rangeslider: {{visible: false}}}}}}, {{displayModeBar: false}});
</script>
"""


def build_report(conn: sqlite3.Connection, output_path: Path = None) -> Path:
    rows = fetch_all(
        conn,
        "SELECT c.notes, c.expected_structure_type, c.price_csv_path, r.engine_structure_type, r.confidence, "
        "cmp.recommendation, cmp.recommendation_basis, cmp.rule_differences_json, cmp.primary_agreement "
        "FROM benchmark_charts c JOIN benchmark_runs r ON r.chart_id = c.chart_id "
        "JOIN benchmark_comparisons cmp ON cmp.run_id = r.run_id "
        "WHERE cmp.primary_agreement = 0 ORDER BY c.expected_structure_type",
    )

    cases_html = []
    for idx, row in enumerate(rows):
        df = pd.read_csv(row["price_csv_path"])
        df.columns = [c.lower() for c in df.columns]
        badge_class = {
            "Engine correct": "correct", "Reference correct": "refcorrect",
            "Ambiguous": "ambiguous", "Not independently verifiable": "unverified",
        }.get(row["recommendation"], "unverified")
        rule_diffs = json.loads(row["rule_differences_json"])

        cases_html.append(_CASE_TEMPLATE.format(
            name=row["expected_structure_type"], badge_class=badge_class,
            recommendation=row["recommendation"], expected=row["expected_structure_type"],
            engine_type=row["engine_structure_type"], confidence=row["confidence"],
            rule_differences="; ".join(rule_diffs) if rule_diffs else "(none)",
            idx=idx, basis=row["recommendation_basis"],
            bars_x=json.dumps(list(range(len(df)))),
            bars_open=json.dumps(df["open"].round(3).tolist()),
            bars_high=json.dumps(df["high"].round(3).tolist()),
            bars_low=json.dumps(df["low"].round(3).tolist()),
            bars_close=json.dumps(df["close"].round(3).tolist()),
        ))

    html = _PAGE.format(cases="\n".join(cases_html))
    output_path = output_path or (Path(__file__).parent / "discrepancy_report.html")
    output_path.write_text(html)
    return output_path


if __name__ == "__main__":
    with connect() as conn:
        path = build_report(conn)
    print(f"discrepancy report written to {path}")
