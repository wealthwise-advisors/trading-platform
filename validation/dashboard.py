"""Expert Chart Validation Framework -- visual dashboard generator (Task 8,
requirement 7). Self-contained HTML, Plotly, theme-aware (light/dark),
using the validated default categorical/sequential palette. Every panel
that only needs engine output (confidence distribution, quality by
structure type, coverage by market/timeframe) is fully populated from the
369 real analyses; panels that need review data (accuracy by market/
timeframe, most common errors, reviewer agreement) render honestly against
whatever is in the `reviews` table -- currently 5 illustrative entries,
clearly labeled as such, not a certified expert sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3
from collections import Counter
from datetime import datetime

from validation.db import connect, fetch_all
from validation import metrics as metrics_mod

_PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Elliott Wave Expert Chart Validation Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
.viz-root {{
  color-scheme: light;
  --surface-1: #fcfcfb; --page: #f9f9f7;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #898781;
  --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --series-2: #008300; --series-3: #e87ba4; --series-4: #eda100;
  --series-5: #1baf7a; --series-6: #eb6834; --status-good: #0ca30c; --status-warn: #fab219;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark;
    --surface-1: #1a1a19; --page: #0d0d0d;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #898781;
    --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --series-2: #008300; --series-3: #d55181; --series-4: #c98500;
    --series-5: #199e70; --series-6: #d95926; --status-good: #0ca30c; --status-warn: #fab219;
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark;
  --surface-1: #1a1a19; --page: #0d0d0d;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #898781;
  --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
  --series-1: #3987e5; --series-2: #008300; --series-3: #d55181; --series-4: #c98500;
  --series-5: #199e70; --series-6: #d95926; --status-good: #0ca30c; --status-warn: #fab219;
}}
body {{ margin: 0; background: var(--page); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
.viz-root {{ padding: 24px; }}
h1 {{ color: var(--text-primary); font-size: 20px; margin: 0 0 4px; }}
.subtitle {{ color: var(--text-secondary); font-size: 13px; margin-bottom: 20px; }}
.banner {{ background: var(--surface-1); border: 1px solid var(--border); border-left: 4px solid var(--status-warn);
          border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; color: var(--text-primary); font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
.card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
.card h2 {{ font-size: 14px; color: var(--text-primary); margin: 0 0 8px; }}
.stat {{ font-size: 32px; font-weight: 600; color: var(--text-primary); }}
.stat-label {{ font-size: 12px; color: var(--text-muted); }}
</style>
</head>
<body>
<div class="viz-root">
<h1>Elliott Wave Expert Chart Validation Dashboard</h1>
<div class="subtitle">{n_analyses} analyses across {n_markets} real markets x {n_timeframes} timeframes &middot; generated {generated_at}</div>
<div class="banner">{review_banner}</div>
<div class="grid">
  <div class="card"><h2>Coverage by market</h2><div id="market-chart"></div></div>
  <div class="card"><h2>Coverage by timeframe</h2><div id="timeframe-chart"></div></div>
  <div class="card"><h2>Confidence distribution (engine output, all analyses)</h2><div id="confidence-chart"></div></div>
  <div class="card"><h2>Quality by structure type (engine output, all analyses)</h2><div id="quality-chart"></div></div>
  <div class="card"><h2>Accuracy by verdict {review_caveat_short}</h2><div id="accuracy-chart"></div></div>
  <div class="card"><h2>Most common error flags {review_caveat_short}</h2><div id="errors-chart"></div></div>
  <div class="card">
    <h2>Reviewer agreement</h2>
    <div class="stat">{agreement_stat}</div>
    <div class="stat-label">{agreement_label}</div>
  </div>
  <div class="card">
    <h2>Hard-rule compliance (independent re-audit, all analyses)</h2>
    <div class="stat">{compliance_stat}</div>
    <div class="stat-label">{compliance_label}</div>
  </div>
</div>
</div>
<script>
const palette = ['#2a78d6', '#008300', '#e87ba4', '#eda100', '#1baf7a', '#eb6834', '#4a3aa7', '#e34948'];
const layoutBase = {{
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{color: '#898781', size: 11}}, margin: {{t: 10, r: 10, b: 40, l: 40}},
  xaxis: {{gridcolor: '#e1e0d922'}}, yaxis: {{gridcolor: '#e1e0d922'}},
  height: 260,
}};

Plotly.newPlot('market-chart', [{{
  type: 'bar', x: {market_labels}, y: {market_counts}, marker: {{color: palette[0]}},
}}], layoutBase, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('timeframe-chart', [{{
  type: 'bar', x: {timeframe_labels}, y: {timeframe_counts}, marker: {{color: palette[4]}},
}}], layoutBase, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('confidence-chart', [{{
  type: 'histogram', x: {confidence_values}, marker: {{color: palette[0]}}, nbinsx: 20,
}}], layoutBase, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('quality-chart', [{{
  type: 'bar', x: {quality_types}, y: {quality_means}, marker: {{color: [palette[0],palette[1],palette[2],palette[3]]}},
}}], layoutBase, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('accuracy-chart', [{{
  type: 'bar', x: {verdict_labels}, y: {verdict_counts},
  marker: {{color: {verdict_labels}.map(v => v === 'Correct' ? '#0ca30c' : v === 'Incorrect' ? '#e34948' : v === 'Ambiguous' ? '#fab219' : '#2a78d6')}},
}}], layoutBase, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('errors-chart', [{{
  type: 'bar', x: {error_labels}, y: {error_counts}, marker: {{color: palette[5]}},
}}], {{...layoutBase, xaxis: {{...layoutBase.xaxis, tickangle: -30}}}}, {{displayModeBar: false, responsive: true}});
</script>
</body></html>
"""


def build_dashboard(conn: sqlite3.Connection, output_path: Path = None) -> Path:
    charts_meta = fetch_all(conn, "SELECT market, timeframe FROM charts")
    market_counts = Counter(c["market"] for c in charts_meta)
    tf_order = ["5m", "15m", "1h", "4h", "1d"]
    tf_counts = Counter(c["timeframe"] for c in charts_meta)

    confidence_values = [r["confidence"] for r in fetch_all(conn, "SELECT confidence FROM analyses WHERE confidence IS NOT NULL")]

    summary = metrics_mod.full_summary(conn)
    qsd = summary["quality_score_distribution"]
    quality_types = ["impulse", "corrective", "triangle", "diagonal"]
    quality_means = [qsd[f"{t}_quality"]["mean"] if qsd[f"{t}_quality"] else 0 for t in quality_types]

    review_count = summary["review_count"]
    struct_acc = summary["structure_accuracy"]
    verdict_labels = list(struct_acc["by_verdict"].keys()) if struct_acc else []
    verdict_counts = list(struct_acc["by_verdict"].values()) if struct_acc else []

    error_flags = ["false_positive", "false_negative", "mis_numbering", "wrong_degree",
                  "missed_triangle", "missed_diagonal", "wrong_correction"]
    # Suppressed below (bandit B608, SQL-injection-shaped f-string): every
    # interpolated name comes from `error_flags` above, a hardcoded
    # literal list defined two lines up, never from request/user input.
    # Verified in docs/SECURITY_AUDIT.md.
    error_counts_rows = fetch_all(conn, f"SELECT {', '.join('SUM('+f+') as '+f for f in error_flags)} FROM reviews")  # nosec B608
    error_counts = [error_counts_rows[0][f] or 0 for f in error_flags] if error_counts_rows and error_counts_rows[0][error_flags[0]] is not None else [0] * len(error_flags)  # noqa: E501

    ra = summary["reviewer_agreement"]
    if review_count == 0:
        review_banner = ("<strong>No expert reviews recorded yet.</strong> Coverage, confidence, and quality "
                         "panels below are genuine engine output across all 369 populated analyses. "
                         "Accuracy/error panels will populate once a qualified reviewer completes the review "
                         "gallery workflow (see README.md) -- they are never fabricated placeholders.")
        review_caveat_short = "(no reviews yet)"
    else:
        illustrative = all("illustrative-demo" in (r["reviewer"] or "") for r in fetch_all(conn, "SELECT DISTINCT reviewer FROM reviews"))
        if illustrative:
            review_banner = (f"<strong>{review_count} reviews recorded -- ILLUSTRATIVE DEMO DATA ONLY.</strong> "
                             "These are the framework author's own rule-consistency spot-checks used to prove the "
                             "pipeline works end-to-end, explicitly NOT a certified Elliott Wave expert review. "
                             "Do not treat the accuracy/error numbers below as validated engine accuracy.")
        else:
            review_banner = f"<strong>{review_count} reviews recorded.</strong>"
        review_caveat_short = "(illustrative demo data)" if illustrative else ""

    if ra and ra["pairwise_agreement_rate"] is not None:
        agreement_stat = f"{ra['pairwise_agreement_rate']:.0%}"
        agreement_label = f"{ra['analyses_with_multiple_reviews']} analyses with 2+ reviewers"
    else:
        agreement_stat = "N/A"
        agreement_label = "no analysis has been reviewed by more than one reviewer yet"

    hrc = summary["hard_rule_compliance"]
    compliance_stat = f"{hrc['hard_rule_compliance_rate']:.0%}" if hrc["hard_rule_compliance_rate"] is not None else "N/A"
    compliance_label = f"{hrc['analyses_with_violations']} of {hrc['total_analyses']} analyses show a violation on re-audit"

    html = _PAGE.format(
        n_analyses=len(charts_meta), n_markets=len(market_counts), n_timeframes=len(tf_counts),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        review_banner=review_banner, review_caveat_short=review_caveat_short,
        market_labels=json.dumps(sorted(market_counts.keys())),
        market_counts=json.dumps([market_counts[m] for m in sorted(market_counts.keys())]),
        timeframe_labels=json.dumps(tf_order),
        timeframe_counts=json.dumps([tf_counts.get(t, 0) for t in tf_order]),
        confidence_values=json.dumps(confidence_values),
        quality_types=json.dumps(quality_types),
        quality_means=json.dumps(quality_means),
        verdict_labels=json.dumps(verdict_labels),
        verdict_counts=json.dumps(verdict_counts),
        error_labels=json.dumps(error_flags),
        error_counts=json.dumps(error_counts),
        agreement_stat=agreement_stat, agreement_label=agreement_label,
        compliance_stat=compliance_stat, compliance_label=compliance_label,
    )
    output_path = output_path or (Path(__file__).parent / "dashboard.html")
    output_path.write_text(html)
    return output_path


if __name__ == "__main__":
    with connect() as conn:
        path = build_dashboard(conn)
    print(f"dashboard written to {path}")
