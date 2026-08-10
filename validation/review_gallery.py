"""Expert Chart Validation Framework -- review gallery generator (Task 8,
requirement 3). Produces ONE self-contained HTML file with an embedded
Plotly candlestick + Elliott Wave overlay for a batch of charts, and a
review form matching the reviews table schema exactly. No backend
required to REVIEW: the page runs entirely client-side and exports
completed reviews as a CSV download; `ingest_reviews.py` loads that CSV
back into the database. Selecting which charts go in a batch (rather than
embedding all 369+ at once) keeps the page fast to load -- run this
multiple times with different filters to cover the full corpus.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3

import pandas as pd

from validation.db import connect, fetch_all

_TEMPLATE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Elliott Wave Expert Review Gallery</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; margin: 0; display: flex; height: 100vh; }}
  #chart-pane {{ flex: 3; padding: 12px; display: flex; flex-direction: column; }}
  #review-pane {{ flex: 1; padding: 16px; border-left: 1px solid #ccc; overflow-y: auto; min-width: 320px; }}
  #plot {{ flex: 1; }}
  h2 {{ margin: 4px 0; font-size: 15px; }}
  .meta {{ font-size: 12px; color: #444; line-height: 1.5; }}
  fieldset {{ margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; }}
  label {{ display: block; margin: 4px 0; font-size: 13px; }}
  button {{ padding: 8px 14px; margin: 4px 4px 4px 0; cursor: pointer; }}
  textarea {{ width: 100%; box-sizing: border-box; }}
  #progress {{ font-size: 12px; color: #666; }}
</style>
</head>
<body>
<div id="chart-pane">
  <h2 id="chart-title"></h2>
  <div class="meta" id="chart-meta"></div>
  <div id="plot"></div>
</div>
<div id="review-pane">
  <div id="progress"></div>
  <label>Reviewer name: <input id="reviewer" type="text" placeholder="your name"></label>
  <fieldset>
    <legend>Verdict</legend>
    <label><input type="radio" name="verdict" value="Correct"> Correct</label>
    <label><input type="radio" name="verdict" value="Acceptable Alternate"> Acceptable Alternate</label>
    <label><input type="radio" name="verdict" value="Incorrect"> Incorrect</label>
    <label><input type="radio" name="verdict" value="Ambiguous"> Ambiguous</label>
  </fieldset>
  <fieldset>
    <legend>Error flags</legend>
    <label><input type="checkbox" id="false_positive"> False positive (labeled something not there)</label>
    <label><input type="checkbox" id="false_negative"> False negative (missed a real structure)</label>
    <label><input type="checkbox" id="mis_numbering"> Mis-numbering (shape right, numbers wrong)</label>
    <label><input type="checkbox" id="wrong_degree"> Wrong degree</label>
    <label><input type="checkbox" id="missed_triangle"> Missed triangle</label>
    <label><input type="checkbox" id="missed_diagonal"> Missed diagonal</label>
    <label><input type="checkbox" id="wrong_correction"> Wrong correction type</label>
  </fieldset>
  <label>Notes:<textarea id="notes" rows="4"></textarea></label>
  <button onclick="submitReview()">Submit &amp; Next</button>
  <button onclick="skipChart()">Skip</button>
  <button onclick="downloadCsv()">Download CSV of all reviews so far</button>
</div>
<script>
const CHARTS = {charts_json};
let idx = 0;
const reviews = [];

function render() {{
  if (idx >= CHARTS.length) {{
    document.getElementById('chart-title').textContent = 'All charts in this batch reviewed.';
    document.getElementById('plot').innerHTML = '';
    document.getElementById('chart-meta').textContent = '';
    document.getElementById('progress').textContent = reviews.length + ' reviews recorded -- click Download CSV.';
    return;
  }}
  const c = CHARTS[idx];
  document.getElementById('progress').textContent = `Chart ${{idx+1}} / ${{CHARTS.length}}`;
  document.getElementById('chart-title').textContent = `${{c.market}} ${{c.timeframe}}  (${{c.bar_count}} bars)`;
  document.getElementById('chart-meta').innerHTML =
    `n_swings=${{c.n_swings}}  bias=${{c.bias}}  cycle=${{c.cycle_position}}<br>` +
    `impulse_quality=${{c.impulse_quality}}  corrective_quality=${{c.corrective_quality}}  ` +
    `triangle_quality=${{c.triangle_quality}}  diagonal_quality=${{c.diagonal_quality}}<br>` +
    `confidence=${{c.confidence}}  warnings=${{JSON.stringify(c.warnings)}}<br>` +
    `alternates=${{JSON.stringify(c.alternates)}}<br>` +
    `recursive_verification=${{JSON.stringify(c.recursive_verification)}}<br>` +
    `rule_violations=${{JSON.stringify(c.rule_violations)}}`;

  const candle = {{
    type: 'candlestick', x: c.bars.map((b,i)=>i),
    open: c.bars.map(b=>b.open), high: c.bars.map(b=>b.high),
    low: c.bars.map(b=>b.low), close: c.bars.map(b=>b.close),
    name: 'price',
  }};
  const waveX = c.wave_sequence.map(w => w.bar);
  const waveY = c.wave_sequence.map(w => w.price);
  const waveText = c.wave_sequence.map(w => w.wave);
  const overlay = {{
    type: 'scatter', mode: 'markers+text', x: waveX, y: waveY, text: waveText,
    textposition: 'top center', marker: {{size: 7, color: 'blue'}}, name: 'wave count',
  }};
  Plotly.newPlot('plot', [candle, overlay], {{
    height: 560, xaxis: {{rangeslider: {{visible: false}}, title: 'bar'}}, yaxis: {{title: 'price'}},
    margin: {{t: 20}},
  }});

  document.querySelectorAll('input[type=radio]').forEach(r => r.checked = false);
  document.querySelectorAll('input[type=checkbox]').forEach(c => c.checked = false);
  document.getElementById('notes').value = '';
}}

function collectFlags() {{
  const verdictEl = document.querySelector('input[name=verdict]:checked');
  return {{
    analysis_id: CHARTS[idx].analysis_id,
    reviewer: document.getElementById('reviewer').value || '(unnamed)',
    verdict: verdictEl ? verdictEl.value : '',
    false_positive: document.getElementById('false_positive').checked ? 1 : 0,
    false_negative: document.getElementById('false_negative').checked ? 1 : 0,
    mis_numbering: document.getElementById('mis_numbering').checked ? 1 : 0,
    wrong_degree: document.getElementById('wrong_degree').checked ? 1 : 0,
    missed_triangle: document.getElementById('missed_triangle').checked ? 1 : 0,
    missed_diagonal: document.getElementById('missed_diagonal').checked ? 1 : 0,
    wrong_correction: document.getElementById('wrong_correction').checked ? 1 : 0,
    notes: document.getElementById('notes').value,
  }};
}}

function submitReview() {{
  const r = collectFlags();
  if (!r.verdict) {{ alert('Pick a verdict first.'); return; }}
  reviews.push(r);
  idx++;
  render();
}}

function skipChart() {{ idx++; render(); }}

function downloadCsv() {{
  const cols = ['analysis_id','reviewer','verdict','false_positive','false_negative',
               'mis_numbering','wrong_degree','missed_triangle','missed_diagonal',
               'wrong_correction','notes'];
  let csv = cols.join(',') + '\\n';
  reviews.forEach(r => {{
    csv += cols.map(k => '"' + String(r[k]).replace(/"/g,'""') + '"').join(',') + '\\n';
  }});
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'reviews_batch.csv';
  a.click();
}}

render();
</script>
</body></html>
"""


def _chart_payload(row: dict) -> dict:
    bars_df = pd.read_csv(row["price_csv_path"])
    bars_df.columns = [c.lower() for c in bars_df.columns]
    return {
        "analysis_id": row["analysis_id"],
        "market": row["market"], "timeframe": row["timeframe"], "bar_count": row["bar_count"],
        "n_swings": row["n_swings"], "bias": row["bias"], "cycle_position": row["cycle_position"],
        "impulse_quality": row["impulse_quality"], "corrective_quality": row["corrective_quality"],
        "triangle_quality": row["triangle_quality"], "diagonal_quality": row["diagonal_quality"],
        "confidence": row["confidence"],
        "warnings": json.loads(row["warnings_json"]),
        "alternates": json.loads(row["alternate_counts_json"]),
        "recursive_verification": json.loads(row["recursive_verification_json"]),
        "rule_violations": json.loads(row["rule_violations_json"]),
        "wave_sequence": json.loads(row["primary_count_json"]),
        "bars": bars_df[["open", "high", "low", "close"]].to_dict(orient="records"),
    }


def build_gallery(conn: sqlite3.Connection, limit: int = 30, market: str = None,
                  timeframe: str = None, output_path: Path = None) -> Path:
    query = "SELECT a.*, c.market, c.timeframe, c.bar_count, c.price_csv_path FROM analyses a JOIN charts c ON a.chart_id = c.chart_id"
    conds, params = [], []
    if market:
        conds.append("c.market = ?")
        params.append(market)
    if timeframe:
        conds.append("c.timeframe = ?")
        params.append(timeframe)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY c.market, c.timeframe LIMIT ?"
    params.append(limit)

    rows = fetch_all(conn, query, tuple(params))
    payload = [_chart_payload(r) for r in rows]

    output_path = output_path or (Path(__file__).parent / "review_gallery.html")
    output_path.write_text(_TEMPLATE.format(charts_json=json.dumps(payload)))
    return output_path


if __name__ == "__main__":
    with connect() as conn:
        path = build_gallery(conn, limit=30)
    print(f"review gallery written to {path}")
