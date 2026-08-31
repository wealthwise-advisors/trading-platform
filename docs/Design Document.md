# Architecture

How the pieces fit and, where it matters, why they are arranged this way.
Requirements are in [Technical Requirements Document.md](Technical%20Requirements%20Document.md); the interface is in [UI_UX.md](UI_UX.md).

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

### The dependency rule

The direction generalises: **`src/` never imports from `api/` or `web/`.**

`src/` is the engine and must be runnable with no HTTP server, no browser and
no framework — that is what makes the CLI runner, the test suite and any
future live process possible. The moment analysis code reaches back into a
router, the engine can only run inside a web request, and every test needs a
server.

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

The Elliott Wave engine is a layered subsystem documented separately:
[ELLIOTT_WAVE.md](ELLIOTT_WAVE.md#architecture).

## Two engines, one strategy interface

`src/backtesting/` holds both engines. They differ only in how they are
driven:

```
BacktestEngine.run(start, end)       # all bars at once, returns full results
ReplayEngine.load(df)                # preload
ReplayEngine.step()  -> FrameState   # exactly one bar, returns a snapshot
ReplayEngine.get_results()           # same BacktestResults shape as above
```

Both use `PaperBroker` and both produce `BacktestResults`, which is what makes
a strategy portable between them without modification.

`ReplayEngine.step()` is deliberately shaped like a broker bar callback. When
live trading is wired up, `LiveTrader` drives the same method with real bars
instead of stored ones — the strategy cannot tell the difference, which is the
point.

### Execution

`PaperBroker` fills at the **next** bar's open plus slippage, never the signal
bar's close. This single decision is what separates a believable backtest from
a flattering one, and it is why the fill model lives in the broker rather than
in each strategy.

`RithmicBroker` raises `NotImplementedError`. A broker that cannot trade must
never look like one that did.

## Data layer (`src/data/`)

Every provider implements `DataProvider` and returns a uniform OHLCV frame, so
the engine is indifferent to origin:

| Provider | Notes |
|---|---|
| `sample_data.py` | Synthetic (GBM + regimes), seeded, no account |
| `csv_provider.py` | Local `data/historical/` files |
| `external_csv_provider.py` | The trader's own archive; chunked, year-file aware |
| `schwab_provider.py` | OAuth2; 30-min access token auto-refreshed |
| `rithmic_provider.py` | Professional futures data; requires an account |

Two behaviours matter more than the list:

- **Availability is measured, not assumed.** `GET /api/data-sources` performs
  real checks — import success, credentials present, token valid — so an
  unusable source is disabled in the UI before a run rather than exploding
  during one.
- **One aggregator.** Coarser timeframes are resampled from finer bars using
  the same code on the historical and live paths. Two aggregators would drift,
  and the drift would appear as a live chart that disagrees with its own
  backtest.

`src/data/schwabdev/` is a vendored third-party client, kept close to upstream
and excluded from lint and type checking. It carries its own MIT licence.

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

Supporting modules:

| Module | Role |
|---|---|
| `deps.py` | Contract specs, configuration loading |
| `store.py` | `backtest_id → BacktestResults`, cached in front of [`db/`](../db/README.md) |
| `strategy_registry.py` | Strategy id/label/param-schema, and the builder |
| `serializers.py` | Results and frames → JSON |
| `schemas/` | Pydantic request/response models |
| `report/` | Self-contained HTML report generation |

### The registry is the contract

`strategy_registry.py` is the single place a strategy announces itself. The
web config form and the Market Grid setup both build their inputs from it, so
adding a strategy adds its UI. Hand-wiring a form per strategy is how the two
surfaces start disagreeing about what a parameter means.

### Results outlive the process

`store.py` is an in-memory cache in front of the SQLite database in
[`db/`](../db/README.md). Every run's scalars and trades become rows; the
equity curve and the OHLCV frame are written as Parquet beside the database,
because two frames of tens of thousands of rows, read back whole or not at all,
would multiply the file size to serve a query nobody makes. Reads come from the
cache first — one dashboard page hits six endpoints for the same id — and fall
back to the database, so a restart no longer 404s every id.

SQLite rather than a server: one file, no port, no password, no monthly bill,
and no way for it to be down while the app is up. What it buys over a folder of
files is the ability to ask questions *across* runs, which is
`db.backtests.summaries()` — symbol, minimum Sharpe, since a date.

Persistence fails soft. An unwritable file, a locked database or a missing
Parquet engine logs and leaves the cache working, because a failed write should
cost history and not the run that just finished. The corollary is that a broken
database is quiet: look for `could not persist backtest` in the logs.

A hand-written schema means a metric added to `BacktestResults` would fail its
`INSERT` — and fail-soft would swallow it. A guard test compares the dataclass
against `PRAGMA table_info` and fails the build naming the field.

## Frontend (`web/`)

React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Zustand + TanStack
Query. `web/src/features/` holds the backtest config/results and live
replay pages; `web/src/components/charts/` has the candlestick chart with
ZigZag/swing overlays (react-plotly.js).

State ownership is split: Zustand for backtest configuration, TanStack Query
for server data, a WebSocket for the replay stream. Server data is not mirrored
into the store — one owner per fact.

Interface behaviour, motion policy and the layout constraints that are easy to
break are in [UI_UX.md](UI_UX.md).

## Request lifecycles

**A backtest**

```
web  ──POST /api/backtests──▶  router  ──▶ provider.load()
                                     └──▶ BacktestEngine.run()
                                              ├── strategy.on_bar() per bar
                                              └── PaperBroker fills next open
                                     ◀──── BacktestResults ──▶ store
web  ◀──── summary + backtest_id ────┘
```

**A replay**

```
web  ══WS /api/replay/{id}══▶  ReplayEngine.load()
        ◀── frame ── step()          one bar per step
        ◀── frame ── step()
              ...
        ◀── live edge reached ──▶  follow-live: poll, closed bars only
```

Follow-live's rules — closed bars only, never silent, pauses respected, gaps
named — are specified in [Technical Requirements Document.md §4.3](Technical Requirements Document.md#43-follow-live). They are
behavioural requirements, not implementation detail, because each one exists
to prevent a specific way of showing the trader something untrue.

## Reporting

`api/report/` generates a self-contained HTML report — chart, metrics and
trades in one file that opens with no Python and no server. It shares its
chart layout with the live UI (`api/report/charts.py` mirrors
`CandlestickChart.tsx`) so a report can be checked against the screen it came
from.

## Configuration

| File | Contents | Committed |
|---|---|---|
| `config/settings.yaml` | Contract specs, capital, log level, data paths | Yes |
| `config/credentials.yaml` | Broker credentials | **No — gitignored** |
| `config/credentials.yaml.example` | Template | Yes |
| `config/schwab_tokens.json` | OAuth2 tokens | **No — gitignored** |

`src/config.py` loads settings and credentials. Details in
[CONFIGURATION.md](CONFIGURATION.md).

> [!CAUTION]
> The process holds live broker credentials. That is why no third-party
> error-reporting service is installed — an exception payload from this
> process is not safe to send anywhere.

## Testing architecture

`tests/` is organised by the behaviour under test, not by module. The suite
splits into three kinds:

| Kind | Examples | What a failure means |
|---|---|---|
| **Unit / engine** | `test_engine.py` | A mechanism broke |
| **Behavioural matrices** | `test_replay_follow_live.py`, `test_follow_live_matrix.py`, `test_multi_replay.py` | A rule about what the user is shown broke |
| **Confirmed baselines** | `test_swing_zigzag_regression.py`, `test_indicator_correctness.py`, `test_reference_platform_parity.py` | Output that was verified against real data changed |

The third kind carries a standing instruction: a failure is *"did I mean to do
this"*, never *"update the expected values"*. Those numbers were confirmed
against real backtests and a reference platform, and re-baselining them
silently discards that verification.

Run `pytest tests/ -v` for the authoritative count; no document should be
trusted over the suite itself.

## Build and deploy

```
push to master
   │
   ├── CI ──── lint (ruff) · type check (mypy) · unit tests
   │            security audit (bandit + pip-audit)
   │            frontend (vitest + tsc + oxlint) · package build
   │
   └── Deploy ── indicator correctness (blocks the deploy)
                 build image → push → pull and rebuild on EC2
                 wait for health → VERIFY the deployed commit
                 smoke test → close SSH
```

`ruff check .` is enforced locally too, by a pre-commit hook running the
identical command against the same `[tool.ruff]` config, so lint failures are
caught before they reach CI rather than 90 seconds after.

The deploy's most important step is the one that asserts `/api/version`
reports the commit that was just built. Without it a container that kept
running, kept port 80 and answered every health check would let the deploy
report success while still serving the previous build.

Serving is nginx (static frontend) plus the FastAPI app behind it, single
origin, so the browser makes no cross-origin requests.

---

<sub>[⬅ Back to docs](README.md)</sub>
