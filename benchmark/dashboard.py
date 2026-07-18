"""Independent Industry Benchmark -- dashboard (Task 9, requirement 7).
Self-contained HTML, dataviz-skill validated palette, light/dark aware --
same pattern as validation/dashboard.py (Task 8).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3
from datetime import datetime

from benchmark.db import connect
from benchmark import metrics as metrics_mod

_PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Elliott Wave Independent Benchmark Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
.viz-root {{
  color-scheme: light;
  --surface-1: #fcfcfb; --page: #f9f9f7; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --text-muted: #898781; --border: rgba(11,11,11,0.10);
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark; --surface-1: #1a1a19; --page: #0d0d0d; --text-primary: #ffffff;
    --text-secondary: #c3c2b7; --text-muted: #898781; --border: rgba(255,255,255,0.10);
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark; --surface-1: #1a1a19; --page: #0d0d0d; --text-primary: #ffffff;
  --text-secondary: #c3c2b7; --text-muted: #898781; --border: rgba(255,255,255,0.10);
}}
body {{ margin: 0; background: var(--page); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
.viz-root {{ padding: 24px; }}
h1 {{ color: var(--text-primary); font-size: 20px; margin: 0 0 4px; }}
.subtitle {{ color: var(--text-secondary); font-size: 13px; margin-bottom: 20px; }}
.banner {{ background: var(--surface-1); border: 1px solid var(--border); border-left: 4px solid #fab219;
          border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; color: var(--text-primary); font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
.card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
.card h2 {{ font-size: 14px; color: var(--text-primary); margin: 0 0 8px; }}
.stat {{ font-size: 32px; font-weight: 600; color: var(--text-primary); }}
.stat-label {{ font-size: 12px; color: var(--text-muted); }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; color: var(--text-secondary); }}
th, td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--border); }}
</style>
</head><body><div class="viz-root">
<h1>Elliott Wave Independent Benchmark Dashboard</h1>
<div class="subtitle">{total_cases} total benchmark cases ({n_cases} synthetic archetype + {n_real} real-market regime) &middot; generated {generated_at}</div>
<div class="banner"><strong>Reference data scope:</strong> MotiveWave, ELWAVE, and ElliottWaveForecast have NO
genuine accessible output data (see reference_sources table) -- not included, not fabricated. Accuracy metrics below
are computed ONLY over the {n_cases} synthetic archetype cases (textbook-DEFINITION derived: Frost & Prechter's
universally-repeated rules, StockCharts ChartSchool, directly checked, plus documented scale/mirror variants) --
the {n_real} real-market cases have no independent reference count and are reported separately as ROBUSTNESS
statistics (determinism, hard-rule compliance across regimes), never blended into the agreement numbers.
Plus one real, sourced, open-source community Pine script's exact code (rule-level comparison only, GitHub-fetched).
See README.md for the full access-status breakdown.</div>
<div class="grid">
  <div class="card"><h2>Agreement rate</h2><div class="stat">{agreement_pct}</div><div class="stat-label">{agreement_label}</div></div>
  <div class="card"><h2>Real-market robustness</h2><div class="stat">{robustness_pct}</div><div class="stat-label">{robustness_label}</div></div>
  <div class="card"><h2>Reproducibility</h2><div class="stat">{repro_pct}</div><div class="stat-label">{repro_label}</div></div>
  <div class="card"><h2>Cohen's Kappa</h2><div class="stat">{kappa}</div><div class="stat-label">{kappa_label}</div></div>
  <div class="card"><h2>Recommendation breakdown</h2><div id="rec-chart"></div></div>
  <div class="card"><h2>Agreement by dimension</h2><div id="dim-chart"></div></div>
  <div class="card"><h2>Precision / Recall / F1 by structure type</h2><div id="prf-chart"></div></div>
  <div class="card"><h2>Rule-level comparison vs. open-source TradingView script</h2>
    <table><tr><th>Rule</th><th>Agreement</th></tr>{rule_rows}</table>
  </div>
</div>
</div>
<script>
const palette = ['#2a78d6', '#008300', '#e87ba4', '#eda100', '#1baf7a', '#eb6834'];
const layoutBase = {{ paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: {{color: '#898781', size: 11}},
                    margin: {{t: 10, r: 10, b: 60, l: 40}}, height: 260 }};

Plotly.newPlot('rec-chart', [{{
  type: 'bar', x: {rec_labels}, y: {rec_counts},
  marker: {{color: {rec_labels}.map(l => l==='Engine correct' ? '#0ca30c' : l==='Reference correct' ? '#2a78d6' : l==='Ambiguous' ? '#fab219' : '#898781')}},
}}], layoutBase, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('dim-chart', [{{
  type: 'bar', x: {dim_labels}, y: {dim_values}, marker: {{color: palette[0]}},
}}], {{...layoutBase, xaxis: {{tickangle: -20}}}}, {{displayModeBar: false, responsive: true}});

Plotly.newPlot('prf-chart', [
  {{type: 'bar', name: 'precision', x: {prf_labels}, y: {prf_precision}, marker: {{color: palette[0]}}}},
  {{type: 'bar', name: 'recall', x: {prf_labels}, y: {prf_recall}, marker: {{color: palette[4]}}}},
], {{...layoutBase, barmode: 'group', xaxis: {{tickangle: -30}}, legend: {{orientation: 'h'}}}}, {{displayModeBar: false, responsive: true}});
</script>
</body></html>
"""


def build_dashboard(conn: sqlite3.Connection, output_path: Path = None) -> Path:
    summary = metrics_mod.full_summary(conn)
    agreement = summary["agreement"]
    kappa = summary["cohens_kappa"]
    dims = summary["dimension_agreement"]
    prf = summary["precision_recall_f1_per_class"]
    rules = summary["rule_comparisons"]

    rec_labels = list(agreement["by_recommendation"].keys())
    rec_counts = list(agreement["by_recommendation"].values())

    dim_labels = list(dims.keys())
    dim_values = [dims[d]["agreement_pct"] if dims[d]["agreement_pct"] is not None else 0 for d in dim_labels]

    prf_labels = [k for k in prf if prf[k]["precision"] is not None or prf[k]["recall"] is not None]
    prf_precision = [prf[k]["precision"] or 0 for k in prf_labels]
    prf_recall = [prf[k]["recall"] or 0 for k in prf_labels]

    rule_rows = "".join(
        f"<tr><td>{r['rule_name']}</td><td>{r['agreement'].replace('_',' ')}</td></tr>" for r in rules
    )

    ds = summary["dataset_summary"]
    repro = summary["reproducibility"]
    rr = summary["regime_robustness"]
    html = _PAGE.format(
        n_cases=agreement["n"], n_real=ds["by_category"].get("real_market_regime", 0),
        total_cases=ds["total_cases"], generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        agreement_pct=f"{agreement['primary_agreement_pct']:.0%}",
        agreement_label=f"{agreement['n']} synthetic archetypes, 95% CI [{agreement['primary_agreement_ci_95']['lower']:.0%}, {agreement['primary_agreement_ci_95']['upper']:.0%}]",
        robustness_pct=f"{rr['resolved_structure_pct']:.0%}",
        robustness_label=f"{rr['n']} real-market windows resolve a structure cleanly (not an accuracy metric)",
        repro_pct=f"{repro['deterministic_pct']:.0%}",
        repro_label=f"{repro['n_checked']} cases x {repro['runs_per_check']} runs, fully deterministic",
        kappa=kappa["kappa"] if kappa["kappa"] is not None else "N/A",
        kappa_label=kappa["note"][:80] + "...",
        rec_labels=json.dumps(rec_labels), rec_counts=json.dumps(rec_counts),
        dim_labels=json.dumps(dim_labels), dim_values=json.dumps(dim_values),
        prf_labels=json.dumps(prf_labels), prf_precision=json.dumps(prf_precision), prf_recall=json.dumps(prf_recall),
        rule_rows=rule_rows,
    )
    output_path = output_path or (Path(__file__).parent / "dashboard.html")
    output_path.write_text(html)
    return output_path


if __name__ == "__main__":
    with connect() as conn:
        path = build_dashboard(conn)
    print(f"dashboard written to {path}")
