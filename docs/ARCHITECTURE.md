# Architecture

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│  web/            React + TypeScript frontend (Vite, Tailwind) │
├─────────────────────────────────────────────────────────────┤
│  api/             FastAPI service -- routers, schemas, export  │
│  cli/              `elliott` CLI -- thin wrapper, same core calls│
├─────────────────────────────────────────────────────────────┤
│  src/analysis/       Elliott Wave engine (see below)            │
│  src/backtesting/     BacktestEngine, ReplayEngine               │
│  src/strategies/       MA Crossover, RSI, Breakout, RSI Divergence│
│  src/broker/, src/data/  PaperBroker/RithmicBroker, data providers│
├─────────────────────────────────────────────────────────────┤
│  benchmark/, validation/   QA layers -- measure the engine, never│
│                             imported BY the engine (one-directional)│
└─────────────────────────────────────────────────────────────┘
```

`src/analysis/` has no dependency on `api/`, `cli/`, `benchmark/`, or
`validation/` — those four all depend on it, never the reverse. This is
what lets `elliott analyze` run the exact same engine the API and the
benchmark use, with zero duplication.

## The Elliott Wave engine (`src/analysis/`)

Built up over nine development tasks, each adding one layer without
touching the ones below it:

```
swing_identification.py     N-bar fractal pivot detection (Swing, SwingType)
        │
        ├── elliott_wave.py         Impulse validation (3 hard rules) + simple ABC zigzag
        ├── corrective_waves.py     Flat variants, zigzag classification (classify_abc)
        ├── fibonacci.py            Soft confidence scoring, confluence zones
        ├── candlestick_patterns.py, chart_patterns.py, regime.py, indicators.py, zigzag.py
        │       (supporting/independent utilities, not part of the core wave-count chain)
        │
        ├── complex_corrections.py  Triangles (detect_triangle) + WXY/WXYXZ combinations
        │                            (find_combinations, find_triangle_candidates)
        ├── diagonal_waves.py       Leading/ending diagonal detection + forward-context
        │                            position classification (_try_diagonal_shape)
        │
        ├── structure_classification.py   Unified scoring: scores impulse/correction/
        │                                  triangle/complex_correction/diagonal hypotheses
        │                                  TOGETHER per swing position (classify_structure_detailed)
        ├── recursive_structure.py         Generic, detector-agnostic recursive verification --
        │                                  recurses into every qualifying sub-window, not just
        │                                  the largest; explicit UNKNOWN on any miss
        │
        └── wave_numbering.py       Top-level candidate generation + DP-based interval
                                      scheduling (_select_best_counts) -- picks the
                                      chart-wide dominant structure(s) from everything above
                                      │
                                      └── wave_analysis.py   Public entry point: analyze(),
                                                              analyze_degrees() -- what api/,
                                                              cli/, and benchmark/ all call
```

### Design principles (established across Tasks 1-9, still true in v1.0.0)

- **Hard rules vs. soft scoring.** Wave 2 retracement bound, Wave 3
  never-shortest, Wave 4 non-overlap (reversed for diagonals) are hard
  gates — violating one means the count is rejected outright, never just
  scored lower. Fibonacci ratios are a soft confidence signal layered on
  top, never a gate.
- **Two independent measurements per structure.** `direct_detection`
  (does the specific pattern's own detector confirm it at its intended
  span) and `engine_structure_type` (does it win chart-wide top-level
  dominance) answer different questions — both are exposed because
  several real, confirmed findings (see
  [benchmark/TASK9_IMPROVEMENT_REPORT.md](../benchmark/TASK9_IMPROVEMENT_REPORT.md))
  are only visible when both are measured.
- **Explicit UNKNOWN over a guess.** `recursive_structure.py` returns
  `confidence=0.0, resolved_type=None` rather than forcing a low-confidence
  label when nothing qualifies.
- **Fractal pivot confirmation.** `identify_swings` needs `left`/`right`
  CONFIRMING bars on both sides of a pivot — a pivot at the very start or
  end of a price series needs deliberately-constructed leading/trailing
  bars to be detected at all. This tripped up test-fixture and benchmark
  construction multiple times (documented in `tests/elliott/conftest.py`
  and `benchmark/pipeline.py`) — it is not a bug, but a real gotcha for
  anyone building new fixtures.

## QA layers

- **`tests/elliott/`** — 56-test pytest regression suite: canonical
  Elliott cases per pattern type, prior-bugfix regressions, performance
  bounds, determinism, and in-process FastAPI `TestClient` checks. Run via
  `elliott validate` or `pytest tests/elliott -v`.
- **`validation/`** — expert chart-validation framework: a SQLite-backed
  pipeline that ran the engine against 369 real charts (5 symbols × 5
  timeframes) for manual visual review, with a scorecard, dashboards, and
  export formats.
- **`benchmark/`** — independent industry benchmark: 473 cases (104
  synthetic archetype variants against textbook Elliott definitions + 369
  real-market robustness cases), agreement statistics, Cohen's Kappa,
  confidence intervals, and a reproducibility harness. See its own
  [README](../benchmark/README.md) and
  [TASK9_IMPROVEMENT_REPORT.md](../benchmark/TASK9_IMPROVEMENT_REPORT.md).

Both are one-directional consumers of `src/analysis/` — neither is
imported by production code, and neither is on the API's request path.

## API (`api/`)

`api/main.py` wires FastAPI routers under `/api`:

| Router | Prefix | Purpose |
|---|---|---|
| `meta` | `/api` | `/health`, `/version`, `/strategies`, `/contracts`, `/data-sources` |
| `backtests` | `/api/backtests` | Run/list/fetch backtests |
| `elliott_wave` | `/api/backtests/{id}/elliott-wave` | Elliott Wave analysis on a stored backtest's price data |
| `replay` | `/api/replay` | WebSocket bar-by-bar replay |
| `schwab` | `/api/schwab` | OAuth2 status/auth-url/complete-auth |
| `optimize` | `/api/optimize` | Parameter sweeps |
| `data_export` | `/api` | CSV/Excel/PDF/Word export (`api/export/formats.py`) |

Full endpoint-level detail: [API_GUIDE.md](API_GUIDE.md).

## Frontend (`web/`)

React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Zustand + TanStack
Query. `web/src/features/` holds the backtest config/results and live
replay pages; `web/src/components/charts/` has the candlestick + Elliott
Wave chart overlays (react-plotly.js).

## CLI (`cli/`)

`cli/main.py` — argparse-based, no new dependency. Every subcommand is a
thin call into the same production code the API uses (`wave_analysis`,
`benchmark`, `tests/elliott` via subprocess, `src.config`). Contains no
Elliott Wave logic of its own.
