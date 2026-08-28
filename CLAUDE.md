# AutoTrader â€” Claude Context Guide

This document tells Claude everything it needs to know to work on this codebase
effectively. Read this before touching any code.

---

## What This Project Is

A **Python futures/options auto-trading platform** with three modes of operation:

| Mode | Entry point | Purpose |
|------|-------------|---------|
| Backtest (batch) | `web/` (React) + `api/` (FastAPI) | Run full backtest, explore results, export HTML report |
| Live Replay | `web/` "Live Replay" page, driven by `api/routers/replay.py` (WebSocket) | Watch strategy trade bar-by-bar in real-time animation |
| Live Trading | `src/live/trader.py` | Connect to Rithmic and trade live (stub â€” not yet wired) |

**Asset class:** Futures (ES, NQ, MES, CL). Options support is planned but not implemented.
**Broker:** Rithmic (R|API+). The live adapter is stubbed â€” backtesting uses `PaperBroker`.
**UI:** React + Tailwind + shadcn/ui frontend, FastAPI backend, Plotly charts. The original
Streamlit app (`ui/`) was fully replaced and deleted â€” only `ui/report.py` and
`ui/components/charts.py` survived (they never depended on Streamlit), now living at
`api/report/report.py` and `api/report/charts.py`.

---

## Environment

- **Python:** 3.12 â€” use `py -3.12` launcher on Windows (not `python` or `py -3`)
- **OS:** Windows 11 (primary dev machine). `pathlib.Path` used throughout so Linux/Mac should work.
- **Shell:** PowerShell (use PowerShell syntax in Bash commands)

### Install dependencies

```powershell
py -3.12 -m pip install -r requirements.txt
```

> `pandas_ta` is available for technical indicators — installed via `requirements.txt`.

---

## Run the apps

```powershell
# FastAPI backend (port 8000) -- run from the repo root
py -3.12 -m uvicorn api.main:app --reload --port 8000

# React frontend (port 5173) -- proxies /api/* to the backend above
cd web
npm run dev

# CLI backtest (quick, no UI)
py -3.12 scripts/run_backtest.py --symbol ES --strategy ma --fast 9 --slow 21

# Generate synthetic data for all symbols
py -3.12 scripts/generate_data.py

# Tests
py -3.12 -m pytest tests/ -v
```

Open `http://localhost:5173` in a browser once both are running -- that's the whole app.

---

## Project Structure

```
Trading/
├── config/
│   ├── settings.yaml              # Contract specs, capital, log level, external_dir
│   ├── credentials.yaml           # Local credentials (gitignored — never commit)
│   ├── credentials.yaml.example   # Committed template — copy and fill in
│   └── schwab_tokens.json         # Schwab OAuth2 tokens (gitignored — never commit)
│
├── src/
│   ├── config.py              # Loads settings.yaml + credentials.yaml
│   │
│   ├── data/
│   │   ├── base_provider.py       # DataProvider ABC + Bar dataclass
│   │   ├── csv_provider.py        # Load OHLCV from data/historical/ CSV files
│   │   ├── external_csv_provider.py  # Load from C:/Data (chunked, year-file aware)
│   │   ├── schwab_provider.py     # Schwab price_history API (OAuth2, auto-refresh)
│   │   ├── schwabdev/             # Schwab API client library (api.py, stream.py)
│   │   ├── rithmic_provider.py    # Download real bars from Rithmic
│   │   └── sample_data.py         # Synthetic data generator (GBM + regimes)
│   │
│   ├── strategies/
│   │   ├── base_strategy.py       # BaseStrategy ABC, Signal, SignalType
│   │   ├── ma_crossover.py        # EMA crossover (fast/slow)
│   │   ├── rsi_mean_reversion.py  # RSI oversold/overbought mean reversion
│   │   ├── breakout.py            # Donchian channel breakout with ATR trailing stop
│   │   └── rsi_divergence.py      # RSI(2) divergence with swing detection
│   │
│   ├── backtesting/
│   │   ├── engine.py          # BacktestEngine — session filter, runs all bars
│   │   ├── replay_engine.py   # ReplayEngine — step-by-step, drives live UI
│   │   ├── results.py         # BacktestResults + Trade dataclasses
│   │   └── metrics.py         # compute_metrics() — Sharpe, Sortino, drawdown, etc.
│   │
│   ├── broker/
│   │   ├── base_broker.py     # BaseBroker ABC, Order, Fill, OrderSide, OrderType
│   │   ├── paper_broker.py    # PaperBroker — simulated fills with slippage
│   │   └── rithmic_broker.py  # RithmicBroker stub
│   │
│   └── live/
│       └── trader.py          # LiveTrader — main loop (stub until Rithmic is wired)
│
├── api/                        # FastAPI backend
│   ├── main.py                 # App entrypoint, mounts all routers under /api
│   ├── deps.py                 # Contract specs, config loading
│   ├── store.py                # (user_id, backtest_id) -> BacktestResults; cache
│   │                           #   in front of the SQLite database in db/
│   ├── auth.py                 # argon2id, sessions, the route guard, throttles
│   ├── oauth.py                # the four sign-in providers and the code exchange
│   ├── verification.py         # Resend: confirmation, reset, username reminder
│   ├── captcha.py              # Cloudflare Turnstile; fails closed when enabled
│   ├── strategy_registry.py    # Strategy id/label/param-schema -> build_strategy()
│   ├── serializers.py          # BacktestResults/DataFrame -> JSON dicts
│   ├── routers/                # backtests, replay, schwab, optimize, meta
│   ├── schemas/                # Pydantic request/response models
│   └── report/                 # HTML report generator (moved from ui/, no Streamlit dep)
│       ├── report.py           # generate_html_report()
│       └── charts.py           # Plotly candlestick + RSI(2)/Stoch/RSI(13) + ZigZag
│
├── web/                        # React frontend (Vite + TS + Tailwind + shadcn/ui)
│   └── src/
│       ├── App.tsx              # Layout shell, Backtest/Live Replay page switch
│       ├── features/            # backtest/ (config form, results page), replay/
│       ├── components/          # charts/, cards/, tables/, ui/ (shadcn primitives)
│       ├── lib/                 # api.ts (typed fetch client), types.ts, insights.ts
│       └── store/               # Zustand config store
│
├── scripts/
│   ├── run_backtest.py            # CLI backtest runner
│   ├── generate_data.py           # Generate synthetic CSV data for all symbols
│   └── download_rithmic_data.py   # Download real Rithmic bars
│
├── tests/                      # 20 files, ~1,715 tests -- see "Tests" below
│   ├── test_auth.py                       # the guard: every route refuses anon
│   ├── test_reset_auth.py                 # password + username recovery
│   ├── test_oauth_auth.py                 # Google · LinkedIn · GitHub · Twitter
│   ├── test_isolation.py                  # one user must not reach another's data
│   ├── conftest.py                        # _SECURITY_SUITES -- read before adding a suite
│   ├── test_engine.py                     # 5 backtest engine smoke tests
│   └── test_swing_zigzag_regression.py    # 29 tests -- regression baseline for the
│                                            #   Swing/3-Leg Deviation zigzag overlay
│                                            #   (boundaries, A-start labeling, parent-
│                                            #   swing containment, live/report parity)
│
├── db/                         # Result database -- see db/README.md
│   ├── schema.sql             # backtests + trades, all IF NOT EXISTS
│   ├── connection.py          # opening the file, PRAGMAs, schema versioning
│   └── backtests.py           # the only module that knows the table layout
│
├── docs/                      # long-form guides; see docs/README.md
├── legacy/                    # superseded code, kept for reference. Not built,
│                              #   not imported, not deployed. Dependabot alerts
│                              #   here are dismissed as not_used.
│
├── data/
│   ├── historical/            # CSV files: {SYMBOL}_{timeframe}.csv  (gitignored)
│   ├── autotrader.db          # SQLite result database (gitignored)
│   └── backtests/             # Parquet sidecars, one dir per backtest_id (gitignored)
│
└── reports/                   # Generated HTML reports (gitignored)
```

---

## Key Concepts

### Contract specs

Defined in `config/settings.yaml` under `contracts:`. Each symbol has:
- `tick_size` â€” minimum price move (ES = 0.25)
- `tick_value` â€” USD value of one tick (ES = $12.50)
- `point_value` â€” USD value of one full point (ES = $50)
- `margin_initial` / `margin_maintenance` â€” for position sizing (not yet enforced)

When adding a new symbol, add its spec here and in the `CONTRACT_SPECS` dicts inside
`api/deps.py` and `scripts/run_backtest.py`.

### BacktestEngine vs ReplayEngine

Both use `PaperBroker` and produce `BacktestResults`. The difference is how they're driven:

```
BacktestEngine.run(start, end)       # runs all bars, returns complete results
ReplayEngine.load(df)                # preloads bars
ReplayEngine.step()  -> FrameState   # processes one bar, returns snapshot
ReplayEngine.get_results()           # builds BacktestResults from current state
```

`ReplayEngine` is used by `api/routers/replay.py` (driven bar-by-bar over a WebSocket
for the React "Live Replay" page). It is also designed to be driven by a live Rithmic
bar callback once that is wired up.

### Writing a new strategy

1. Subclass `BaseStrategy` in `src/strategies/`
2. Implement `on_bar(bars_df, current_bar, position) -> Optional[Signal]`
3. Return `Signal(SignalType.BUY/SELL/CLOSE, ...)`  or `None`
4. Call `reset()` to clear any state between runs
5. Register in `src/strategies/__init__.py`
6. Add to `api/strategy_registry.py`'s `STRATEGIES` list (id/label/param-schema) --
   the React config form and the Live Replay page both read from that registry,
   no per-file sidebar wiring needed

```python
from src.strategies.base_strategy import BaseStrategy, Signal, SignalType
from src.data.base_provider import Bar
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MyStrategy")

    def reset(self):
        pass   # reset any indicators / state here

    def on_bar(self, bars_df: pd.DataFrame, current_bar: Bar, position: int):
        if len(bars_df) < 20:
            return None
        # ... your logic ...
        return Signal(
            signal_type=SignalType.BUY,
            strategy_name=self.name,
            timestamp=current_bar.timestamp,
            price=current_bar.close,
            reason="Your reason here",
        )
```

The engine handles position flipping automatically â€” you just emit BUY/SELL/CLOSE signals.

### PaperBroker fill model

Orders are filled on the **next bar's open** (realistic â€” no look-ahead):
- Market orders: filled at `bar.open Â± slippage_ticks * tick_size`
- Limit orders: filled if `bar.low <= limit_price` (buy) or `bar.high >= limit_price` (sell)
- Stop orders: triggered when price crosses stop level

### HTML report sharing

```python
from api.report.report import generate_html_report
html = generate_html_report(results, output_path="reports/my_report.html")
```

Or use the "Export Report (HTML)" button in the React dashboard (calls
`GET /api/backtests/{id}/report`). The file is ~185 KB, fully self-contained
(CDN Plotly.js), and opens in any browser. No Python
or server needed on the recipient's machine.

---

## Rithmic Historical Data

Real market data is downloaded via `src/data/rithmic_provider.py` using the `pyrithmic` package.

### Setup (once per developer)

**Option A â€” credentials.yaml (recommended):**
```bash
cp config/credentials.yaml.example config/credentials.yaml
# Edit credentials.yaml and set rithmic.credentials_path
```

**Option B â€” environment variable:**
```bash
# Windows PowerShell
$env:RITHMIC_CREDENTIALS_PATH = "C:\path\to\credentials"

# macOS / Linux
export RITHMIC_CREDENTIALS_PATH=/path/to/credentials
```

**Option C â€” .env file in project root:**
```
RITHMIC_CREDENTIALS_PATH=/path/to/credentials
```

The credentials directory must contain a `RITHMIC_LIVE.ini` file from Rithmic.

### Exchange codes

| Symbol | Exchange |
|--------|----------|
| ES, NQ, MES, MNQ | CME |
| CL, NG, MCL | NYMEX |
| GC, SI, MGC | COMEX |
| ZN, ZB, ZF, YM | CBOT |

### Download data via CLI

```powershell
py -3.12 scripts/download_rithmic_data.py `
    --symbol ES --timeframe 5m --start 2024-01-01 --end 2024-12-31
```

Optional flags: `--force` (re-download), `--exchange CME`, `--cache-dir data/historical`

### How RithmicDataProvider works

```python
provider = RithmicDataProvider(cache_dir="data/historical")
df = provider.load("ES", start_dt, end_dt, timeframe="5m")
```

1. Resolves credentials path from env var â†’ config/credentials.yaml â†’ .env
2. Checks cache â€” returns if it covers the requested range
3. Connects `RithmicHistoryApi` (standalone; falls back to shared loop with OrderApi)
4. Calls `download_historical_tick_data(symbol, exchange, start, end, bar_type_period)`
5. Normalizes columns (Openâ†’open, etc.)
6. Caches to CSV and returns DataFrame

**Native bar periods:** 1, 3, 5, 8, 10, 15, 20, 30 minutes.
For 1h: downloads 30m bars and resamples OHLCV.

### In the React UI

Select **"Real Data (Rithmic)"** in the Data Source dropdown, then run the backtest.
The provider is imported lazily â€” if `pyrithmic` isn't installed, `GET /api/data-sources`
reports it as unavailable and the dropdown option is disabled.

---

## Wiring Up Rithmic Live Trading

The stub is at `src/broker/rithmic_broker.py`. `pyrithmic` is installed via `requirements.txt`.

Fill in `connect()` inside `RithmicBroker` using the same pattern as
`RithmicDataProvider._ensure_apis()` in `src/data/rithmic_provider.py`.

For live bar streaming, wire the Rithmic bar callback into `LiveTrader._execute_signal()`
in `src/live/trader.py`. The `ReplayEngine.step()` interface is designed to match
the shape of a Rithmic bar event.

---

## Data

Historical data lives in `data/historical/{SYMBOL}_{timeframe}.csv` (gitignored).

Expected CSV format:
```
timestamp,open,high,low,close,volume
2024-01-02 09:30:00,4500.25,4502.00,4499.75,4501.50,342
```

---

## Tests

```powershell
py -3.12 -m pytest tests/ -v
```

**20 files, ~1,715 tests.** The four below are the security suite and have a
rule of their own -- see the warning after them.

| Suite | Holds |
|---|---|
| `test_auth.py` | Every route refuses an anonymous caller. Sessions die on logout. A new account never receives the broker. |
| `test_reset_auth.py` | Recovery leaks nothing -- not by body, status, or timing. Tokens are single-use, expiring, and purpose-scoped. |
| `test_oauth_auth.py` | Only a **provider-verified** address may match an account. A disabled account is refused, never re-provisioned. |
| `test_isolation.py` | One user cannot reach another's data. Routes are swept from the app's own OpenAPI schema. |

> ⚠️ **Adding a test file that asserts a refusal?** Add its name to
> `_SECURITY_SUITES` in [`tests/conftest.py`](tests/conftest.py). Every other
> suite runs with `require_user` overridden to a signed-in user, so without
> that entry your refusal assertions pass **without ever reaching the guard**.

> ⚠️ **Adding an API route?** Two guards will fail, and both are meant to.
> `test_every_api_route_is_either_public_or_guarded` enumerates the schema and
> demands a 401 from anything not in `PUBLIC`; `test_only_one_new_path_added`
> asserts an exact route count. Raise them deliberately rather than by reflex.

`test_engine.py`: 5 tests cover MA crossover, RSI, Breakout, equity curve
length, and trade P&L types (synthetic data, seed=99).

`test_swing_zigzag_regression.py`: 29 tests -- the verified, stable
regression baseline for the Swing (10-Leg) / 3-Leg Deviation zigzag overlay
(`src/analysis/zigzag.py::calc_nested_zigzag()`, its live-chart consumer
`api/serializers.py::zigzag_to_records()`, and its static-report consumer
`api/report/report.py::generate_html_report()`). Confirmed correct via
real backtests, live browser screenshots, and direct API/DOM inspection on
2026-08-02 -- see the module's own docstring. Covers, against three fixed
deterministic reference datasets:

- major swing boundaries are contiguous, non-overlapping, sequential from 1
- every swing's 3-Leg sequence starts at label "A" (never "B")
- no 3-Leg pivot's timestamp falls outside its own parent swing's window
- the live chart and static HTML report use identical deviation defaults
  and produce byte-identical swing/label data for the same input
- a real end-to-end backtest's generated report contains every swing header

A failure here means a change altered one of these already-confirmed
behaviors -- treat that as "did I mean to do this", not "update the test
to match the new output". This is the foundation for future
higher-level market-structure work; don't modify `calc_nested_zigzag()`'s
core containment/labeling logic without re-running and re-confirming
against this suite.

All tests must pass before committing.

---

## Accounts & Access

Registration is open. Signing in is by **username + password**, or by
**Google, LinkedIn, GitHub or Twitter/X**.

| Concern | Where |
|---|---|
| Hashing, sessions, the guard, rate limits | [`api/auth.py`](api/auth.py) |
| Providers, PKCE, token exchange | [`api/oauth.py`](api/oauth.py) |
| Confirmation / reset / reminder mail | [`api/verification.py`](api/verification.py) |
| Turnstile | [`api/captcha.py`](api/captcha.py) |
| Accounts, sessions, identities, tokens | [`db/users.py`](db/users.py) |
| Creating accounts, granting `is_owner` | [`scripts/manage_users.py`](scripts/manage_users.py) |

**Four rules worth knowing before changing any of it:**

1. **An account never grants the broker.** There is one Schwab connection and
   it is the operator's own. `users.is_owner` defaults to `0` and
   `create_user` has no parameter for it, so no route can hand it out.
2. **Only a provider-VERIFIED address may match an account.** An unverified one
   is a claim by whoever is signing in.
3. **No repository function takes a default `user_id`.** A forgotten argument
   is a `TypeError`, not a leak.
4. **Another user's backtest is 404, never 403.** A 403 confirms the id exists.

**Every integration is dormant without credentials** — the provider reports
itself unconfigured and its button says so. Nothing is faked. The deploy prints
`present:` / `ABSENT :` per integration, by presence only.

---

## Data Sources

Four data sources are available in the React sidebar (`api/routers/meta.py`'s
`/data-sources` endpoint reports which are actually usable):

| Option | Provider | Notes |
|--------|----------|-------|
| Synthetic Data | `SampleDataProvider` | GBM-based, no account needed |
| My Historical Data (CSV) | `ExternalCSVProvider` | Reads from `C:/Data` (configurable in `settings.yaml → data.external_dir`) |
| Live Data (Schwab) | `SchwabDataProvider` | OAuth2, 30-min access token auto-refreshed, 7-day refresh token |
| Real Data (Rithmic) | `RithmicDataProvider` | Requires Rithmic account + credentials |

### ExternalCSVProvider

Loads from `C:/Data` (or path in `settings.yaml`). Expected filenames: `ES_FULL.csv`, `ES_FULL_2024.csv`, `FULL_ES.csv`. Year-specific files are preferred (smaller). Input must be 1-minute bars; any coarser timeframe is resampled on the fly.

### SchwabDataProvider

- Credentials in `config/credentials.yaml` under `schwab:` (app_key, app_secret, callback_url)
- Tokens stored in `config/schwab_tokens.json` (gitignored)
- Initial auth: `provider.get_auth_url()` → browser → paste redirect URL → `provider.complete_auth(url)`
- Access token (30 min) is auto-refreshed by a daemon thread inside the `schwabdev.Client`
- Refresh token lasts 7 days — the `SchwabAuthWidget.tsx` sidebar widget (backed by
  `api/routers/schwab.py`) shows expiry and handles re-auth
- Symbol mapping: `ES` → `/ES`, `NQ` → `/NQ`, etc. (automatic for known futures roots)
- Date range is chunked into 30-day windows to stay within Schwab API limits

---

## Strategies

### RSI Divergence (`src/strategies/rsi_divergence.py`)

The primary strategy. Uses RSI(2) divergence with a two-step pre/post-condition entry:

**Bullish setup:**
1. Price makes a lower low AND RSI makes a higher low (divergence) → pre-condition armed
2. Price closes above the high of the divergence bar → BUY entry
3. Exit when RSI > overbought (default 94)

**Bearish setup:**
1. Price makes a higher high AND RSI makes a lower high → pre-condition armed
2. Price closes below the low of the divergence bar → SELL entry
3. Exit when RSI < oversold (default 2)

Key parameters:
- `rsi_period` — default 2 (very sensitive, designed for short-term mean reversion)
- `rsi_overbought` / `rsi_oversold` — exit thresholds (default 94 / 2)
- `swing_lookback` — bars each side to confirm a local swing high/low (default 5)
- `max_divergence_bars` — max gap between swings to count as divergence (default 60)

---

## Chart Panels

The live candlestick chart is `web/src/components/charts/CandlestickChart.tsx` (React,
react-plotly.js) -- it's a full-fidelity port of the old `candlestick_with_trades()`.
The static HTML export version lives at `api/report/charts.py` (same 4-row layout, used
only by the "Export Report" button). Both render 4 rows:

| Row | Content |
|-----|---------|
| 1 (55%) | Candlestick + EMA(9) + EMA(21) + ZigZag overlay + trade markers |
| 2 (15%) | RSI(2) — purple, lines at 94 (red) and 2 (green) |
| 3 (15%) | Stochastic %K/%D — lines at 80/20 |
| 4 (15%) | RSI(13) — amber, lines at 70/30 |

### ZigZag overlay

The swing-numbering math is shared: `src/analysis/zigzag.py`'s `calc_zigzag()` (wraps
`pandas_ta.zigzag()`, requires Python 3.12) and `assign_swing_labels()` (the fixed-channel
per-swing numbering algorithm -- confirmed working, don't change without re-verifying
against real data). Controlled in the React sidebar:
- **3-Leg / 10-Leg Deviation %** sliders — minimum % price move to confirm a new swing

ZigZag is **display only** — it does not affect strategy signals. Red dots = swing highs, green dots = swing lows.

---

## Session Time Filter

`BacktestEngine` accepts `session_start` and `session_end` (`datetime.time` objects). When set, bars outside the window are dropped after loading but before strategy runs. The provider always loads midnight-to-midnight; the engine trims to session hours.

The React sidebar (`ConfigForm.tsx`) has a "Session Hours (EST)" section defaulting to 09:30–16:00.

---

## Known Constraints

- **pandas_ta** is available (Python 3.12). Use `import pandas_ta as ta` for indicators.
- **No live Rithmic connection** — `RithmicBroker` raises `NotImplementedError` until wired.
- **Single-symbol backtests** — the engine runs one symbol at a time.
- **Schwab refresh token** — expires every 7 days; re-auth required via the sidebar widget.
