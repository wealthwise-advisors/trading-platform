# Architecture

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│  web/            React + TypeScript frontend (Vite, Tailwind) │
├─────────────────────────────────────────────────────────────┤
│  api/             FastAPI service -- routers, schemas, export  │
├─────────────────────────────────────────────────────────────┤
│  src/analysis/       Swing/pivot detection, candlestick + chart │
│                        patterns, regime classification          │
│  src/backtesting/     BacktestEngine, ReplayEngine               │
│  src/strategies/       MA Crossover, RSI, Breakout, RSI Divergence│
│  src/broker/, src/data/  PaperBroker/RithmicBroker, data providers│
└─────────────────────────────────────────────────────────────┘
```

`src/analysis/` has no dependency on `api/` — `api/` depends on it, never
the reverse.

## Analysis layer (`src/analysis/`)

```
swing_identification.py     N-bar fractal pivot detection (Swing, SwingType)
                              -- used by api/report/charts.py's ZigZag overlay
                              and src/backtesting/trade_quality.py's setup scoring
candlestick_patterns.py      Doji, hammer, engulfing, morning/evening star
chart_patterns.py            Double top/bottom, head & shoulders, triangle
regime.py                    Market regime classification (used by the
                              regime-adaptive strategy)
indicators.py, zigzag.py     Supporting/independent utilities
```

### Design principles

- **Fractal pivot confirmation.** `identify_swings` needs `left`/`right`
  CONFIRMING bars on both sides of a pivot — a pivot at the very start or
  end of a price series needs deliberately-constructed leading/trailing
  bars to be detected at all. In a backtest you must only ever act on
  `confirm_index`, never `index` — using `index` is look-ahead bias.
- **Local-adaptive minimum-move filtering** — swing filtering evaluates
  each candidate counter-swing against its own local volatility rather
  than one global threshold, so a genuine minor pivot in a low-volatility
  stretch isn't erased by an unrelated volatile stretch elsewhere in the
  same series.

## API (`api/`)

`api/main.py` wires FastAPI routers under `/api`:

| Router | Prefix | Purpose |
|---|---|---|
| `meta` | `/api` | `/health`, `/version`, `/strategies`, `/contracts`, `/data-sources` |
| `backtests` | `/api/backtests` | Run/list/fetch backtests |
| `replay` | `/api/replay` | WebSocket bar-by-bar replay |
| `schwab` | `/api/schwab` | OAuth2 status/auth-url/complete-auth |
| `optimize` | `/api/optimize` | Parameter sweeps |
| `data_export` | `/api` | CSV/Excel/PDF/Word export (`api/export/formats.py`) |

Full endpoint-level detail: [API_GUIDE.md](API_GUIDE.md).

## Frontend (`web/`)

React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Zustand + TanStack
Query. `web/src/features/` holds the backtest config/results and live
replay pages; `web/src/components/charts/` has the candlestick chart with
ZigZag/swing overlays (react-plotly.js).
