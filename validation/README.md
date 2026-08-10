# Elliott Wave Expert Chart Validation Framework (Task 8)

A professional visual validation system built ENTIRELY around the existing,
unmodified Elliott Wave engine (`src/analysis/*.py`). Nothing under `src/`
or `api/` is touched by anything in this directory -- it imports production
code, it never changes it.

## Honesty note (read this first)

**"Expert review" requires a genuine, qualified human Elliott Wave analyst.**
This framework does not, and cannot, fabricate that. What's delivered here
is the complete, working infrastructure -- database, real-data pipeline,
review tool, metrics, exports, dashboard -- populated with 369 real,
engine-computed chart analyses across 5 real markets and all 5 requested
timeframes. The `reviews` table (the actual expert scorecard) ships empty
and ready to use, plus 5 explicitly-labeled ILLUSTRATIVE entries (marked
`reviewer = "illustrative-demo (NOT certified expert review)"`) that exist
only to prove the metrics/export/dashboard pipeline works end-to-end on
real review data, not to claim any structure was expert-validated. Every
dashboard panel and export that depends on real review data says so
explicitly rather than showing a fabricated number.

## Architecture

```
validation/
  schema.sql          SQLite DDL: charts, analyses, reviews (+ indexes)
  db.py                thin SQLite helper (init, insert, query)
  pipeline.py           analyze_chart() -- runs the REAL engine, extracts every
                        field the schema needs; segment_series() -- cuts a long
                        real series into non-overlapping chart instances
  populate.py           driver: fetch real data (Schwab) for ES/NQ/SPY/GC/CL x
                        5m/15m/1h/4h/1d, populate charts+analyses
  metrics.py             precision/recall/F1/accuracy/calibration/agreement --
                        each correctly returns null until real review data exists
  export.py               CSV / Excel / JSON / Markdown, all from one query
  review_gallery.py       generates a self-contained HTML review tool
                        (Plotly candlestick + wave overlay + scorecard form,
                        client-side CSV export, no backend needed to review)
  ingest_reviews.py       loads a completed reviews CSV back into the DB
  dashboard.py             self-contained HTML dashboard, dataviz-skill palette,
                        light/dark aware
  charts/                 per-chart OHLC CSVs (one per chart_id) + per-market
                        source CSVs
  exports/                 CSV/Excel/JSON/Markdown output + the illustrative
                        demo reviews CSV
```

## Database schema

Three tables (full DDL in `schema.sql`):

- **`charts`** -- one row per chart instance: market, timeframe, bar count,
  data source, path to its own OHLC CSV.
- **`analyses`** -- one row per chart's engine analysis: primary count,
  alternates, impulse/corrective/triangle/diagonal quality, confidence,
  recursive verification results, rule violations (independent re-audit),
  warnings, notes. Every field the task's requirement 2 lists.
- **`reviews`** -- one row per human review: verdict (`Correct` /
  `Acceptable Alternate` / `Incorrect` / `Ambiguous`), the seven error
  flags from requirement 4 (false_positive, false_negative, mis_numbering,
  wrong_degree, missed_triangle, missed_diagonal, wrong_correction), notes.

## Review workflow (how a real reviewer uses this)

1. `py -3.12 validation/review_gallery.py` -- generates `review_gallery.html`
   for a batch of charts (default: 30; pass `market=`/`timeframe=`/`limit=`
   to `build_gallery()` for a different batch -- e.g. one gallery per
   market, or per structure type, to work through the full 369).
2. Open the HTML file in a browser. Each chart shows: real candlestick data,
   the engine's wave-count overlay, and every field from the `analyses`
   table (quality scores, confidence, recursive verification, rule
   violations, warnings, alternates) laid out beside it.
3. The reviewer marks a verdict + any error flags + notes, clicks
   **Submit & Next**. Fully client-side -- no server, no account, works
   offline once the page is loaded (only the Plotly CDN script needs network).
4. **Download CSV** at any point (or at the end) to export everything
   reviewed so far.
5. `py -3.12 validation/ingest_reviews.py <downloaded.csv>` loads it into
   the `reviews` table.
6. Re-run `metrics.py` / `export.py` / `dashboard.py` -- they now reflect
   the real review data.

Repeat with more galleries (different batches) to build toward full
coverage. The pipeline already scales to 1000+ -- `populate.py`'s
`WINDOW_BARS` can be lowered (more, smaller charts per series) or the
fetch date range extended (more history → more segments) to grow the
corpus; the current 369 is what real Schwab data access and this session's
time allowed, not a hard ceiling.

## Markets & timeframes -- what's real, what isn't

| Requested | Status |
|---|---|
| ES, NQ, SPY | Real Schwab futures/equity data, all 5 timeframes |
| Gold (GC), Crude Oil (CL) | Real Schwab futures data, all 5 timeframes (verified: plausible price levels, e.g. GC ~$3970-4230, CL ~$67-82) |
| BTC | Schwab returned a "BTC" series, but at ~$48 -- not genuine Bitcoin prices. Excluded rather than used. No real crypto data source is wired into this platform. |
| EURUSD | Schwab returned no data for this symbol -- forex isn't supported by this data provider. Excluded, not fabricated. |

5m/15m/1h/4h/1d are all covered for the 5 available markets. 4h and Daily
are built by resampling real 1h bars (same OHLCV aggregation method
`resample_4h_daily.py`-style logic already used elsewhere in this session),
not independently fetched at native granularity.

## Metrics (requirement 5)

All in `metrics.py`, each documented with exactly what it needs:

- **Structure accuracy**, **wave numbering accuracy** -- need `reviews` data.
- **Hard-rule compliance** -- needs NO review data; an independent re-audit
  computed for every analysis at population time (retracement/extension/
  overlap ratios recomputed from final wave prices and checked against the
  documented gates). Currently **100% compliant across all 369 real charts**
  -- a genuine, useful finding on its own (confirms the engine's hard-rule
  enforcement holds up under an independent check, not just self-report).
- **Confidence calibration** -- buckets `reviews` by the engine's own
  confidence score and reports the accept-rate per bucket; needs review data.
- **Precision / recall / F1** -- generic, parameterized by miss-type flag
  (missed_triangle, missed_diagonal, mis_numbering, wrong_correction,
  wrong_degree); needs review data.
- **Reviewer agreement** -- pairwise verdict-agreement rate among analyses
  reviewed by 2+ people (documented simplification: not Cohen's kappa,
  which needs a larger sample than a pilot review realistically has).

## Export formats (requirement 6)

`export.py` produces all four from one shared query, so they never drift:
CSV (`validation_export.csv`), Excel (`validation_export.xlsx`, with a
second `summary_metrics` sheet), JSON (`validation_export.json`), Markdown
(`validation_report.md`).

## Dashboard (requirement 7)

`dashboard.py` -- self-contained HTML, Plotly, the dataviz skill's
validated default categorical/sequential palette, light/dark aware via
`prefers-color-scheme` + `data-theme`. Panels:
- Coverage by market / by timeframe (real, all 369 analyses)
- Confidence distribution (real, histogram)
- Quality by structure type (real, mean impulse/corrective/triangle/diagonal quality)
- Accuracy by verdict, most common error flags (review-derived -- currently
  the 5 illustrative entries only, with a visible on-page banner saying so)
- Reviewer agreement, hard-rule compliance (stat tiles)

## Example validation report

See `exports/validation_report.md` for the live, real output (369
analyses, 5 illustrative reviews). Regenerate anytime with
`py -3.12 validation/export.py`.
