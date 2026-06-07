# AutoTrader — Claude Context Guide

This document tells Claude everything it needs to know to work on this codebase
effectively. Read this before touching any code.

---

## What This Project Is

A **Python futures/options auto-trading platform** with three modes of operation:

| Mode | Entry point | Purpose |
|------|-------------|---------|
| Backtest (batch) | `ui/app.py` | Run full backtest, explore results, export HTML report |
| Live Replay | `ui/live_app.py` | Watch strategy trade bar-by-bar in real-time animation |
| Live Trading | `src/live/trader.py` | Connect to Rithmic and trade live (stub — not yet wired) |

**Asset class:** Futures (ES, NQ, MES, CL). Options support is planned but not implemented.  
**Broker:** Rithmic (R|API+). The live adapter is stubbed — backtesting uses `PaperBroker`.  
**UI:** Streamlit + Plotly.

---

## Environment

- **Python:** 3.10 — use `py -3.10` launcher on Windows (not `python` or `py -3`)
- **OS:** Windows 11 (primary dev machine). `pathlib.Path` used throughout so Linux/Mac should work.
- **Shell:** PowerShell (use PowerShell syntax in Bash commands)

### Install dependencies

```powershell
py -3.10 -m pip install -r requirements.txt
```

> `pandas-ta` is intentionally excluded — it does not support Python 3.10.
> All technical indicators (EMA, RSI, ATR) are computed inline with pandas/numpy.

---

## Run the apps

```powershell
# Backtest dashboard (port 8501)
py -3.10 -m streamlit run ui/app.py

# Live replay dashboard (port 8502)
py -3.10 -m streamlit run ui/live_app.py --server.port 8502

# CLI backtest (quick, no UI)
py -3.10 scripts/run_backtest.py --symbol ES --strategy ma --fast 9 --slow 21

# Generate synthetic data for all symbols
py -3.10 scripts/generate_data.py

# Tests
py -3.10 -m pytest tests/ -v
```

---

## Project Structure

```
Trading/
├── config/
│   ├── settings.yaml              # Contract specs, capital, log level
│   ├── credentials.yaml           # Local credentials (gitignored — never commit)
│   └── credentials.yaml.example   # Committed template — copy and fill in
│
├── src/
│   ├── config.py              # Loads settings.yaml + credentials.yaml
│   │
│   ├── data/
│   │   ├── base_provider.py   # DataProvider ABC + Bar dataclass
│   │   ├── csv_provider.py    # Load OHLCV from CSV files
│   │   ├── rithmic_provider.py# Download real bars from Rithmic
│   │   └── sample_data.py     # Synthetic data generator (GBM + regimes)
│   │
│   ├── strategies/
│   │   ├── base_strategy.py   # BaseStrategy ABC, Signal, SignalType
│   │   ├── ma_crossover.py    # EMA crossover (fast/slow)
│   │   ├── rsi_mean_reversion.py  # RSI oversold/overbought mean reversion
│   │   └── breakout.py        # Donchian channel breakout with ATR trailing stop
│   │
│   ├── backtesting/
│   │   ├── engine.py          # BacktestEngine — runs all bars at once
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
├── ui/
│   ├── app.py                 # Static backtest dashboard
│   ├── live_app.py            # Bar-by-bar replay dashboard
│   ├── report.py              # HTML report generator (shareable, offline)
│   └── components/
│       ├── charts.py          # Plotly chart builders (candlestick, equity, etc.)
│       └── metrics.py         # Streamlit metric card renderers
│
├── scripts/
│   ├── run_backtest.py        # CLI backtest runner
│   ├── generate_data.py       # Generate synthetic CSV data for all symbols
│   └── download_rithmic_data.py # Download real Rithmic bars
│
├── tests/
│   └── test_engine.py         # 5 smoke tests (all passing)
│
├── data/
│   └── historical/            # CSV files: {SYMBOL}_{timeframe}.csv  (gitignored)
│
└── reports/                   # Generated HTML reports (gitignored)
```

---

## Key Concepts

### Contract specs

Defined in `config/settings.yaml` under `contracts:`. Each symbol has:
- `tick_size` — minimum price move (ES = 0.25)
- `tick_value` — USD value of one tick (ES = $12.50)
- `point_value` — USD value of one full point (ES = $50)
- `margin_initial` / `margin_maintenance` — for position sizing (not yet enforced)

When adding a new symbol, add its spec here and in the `CONTRACT_SPECS` dicts inside
`ui/app.py`, `ui/live_app.py`, and `scripts/run_backtest.py`.

### BacktestEngine vs ReplayEngine

Both use `PaperBroker` and produce `BacktestResults`. The difference is how they're driven:

```
BacktestEngine.run(start, end)       # runs all bars, returns complete results
ReplayEngine.load(df)                # preloads bars
ReplayEngine.step()  -> FrameState   # processes one bar, returns snapshot
ReplayEngine.get_results()           # builds BacktestResults from current state
```

`ReplayEngine` is used by `ui/live_app.py`. It is also designed to be driven by a
live Rithmic bar callback once that is wired up.

### Writing a new strategy

1. Subclass `BaseStrategy` in `src/strategies/`
2. Implement `on_bar(bars_df, current_bar, position) -> Optional[Signal]`
3. Return `Signal(SignalType.BUY/SELL/CLOSE, ...)`  or `None`
4. Call `reset()` to clear any state between runs
5. Register in `src/strategies/__init__.py`
6. Add to the sidebar dropdown in `ui/app.py` and `ui/live_app.py`

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

The engine handles position flipping automatically — you just emit BUY/SELL/CLOSE signals.

### PaperBroker fill model

Orders are filled on the **next bar's open** (realistic — no look-ahead):
- Market orders: filled at `bar.open ± slippage_ticks * tick_size`
- Limit orders: filled if `bar.low <= limit_price` (buy) or `bar.high >= limit_price` (sell)
- Stop orders: triggered when price crosses stop level

### HTML report sharing

```python
from ui.report import generate_html_report
html = generate_html_report(results, output_path="reports/my_report.html")
```

Or use the "Export Report (HTML)" button in the backtest dashboard. The file is
~185 KB, fully self-contained (CDN Plotly.js), and opens in any browser. No Python
or server needed on the recipient's machine.

---

## Rithmic Historical Data

Real market data is downloaded via `src/data/rithmic_provider.py` using the `pyrithmic` package.

### Setup (once per developer)

**Option A — credentials.yaml (recommended):**
```bash
cp config/credentials.yaml.example config/credentials.yaml
# Edit credentials.yaml and set rithmic.credentials_path
```

**Option B — environment variable:**
```bash
# Windows PowerShell
$env:RITHMIC_CREDENTIALS_PATH = "C:\path\to\credentials"

# macOS / Linux
export RITHMIC_CREDENTIALS_PATH=/path/to/credentials
```

**Option C — .env file in project root:**
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
py -3.10 scripts/download_rithmic_data.py `
    --symbol ES --timeframe 5m --start 2024-01-01 --end 2024-12-31
```

Optional flags: `--force` (re-download), `--exchange CME`, `--cache-dir data/historical`

### How RithmicDataProvider works

```python
provider = RithmicDataProvider(cache_dir="data/historical")
df = provider.load("ES", start_dt, end_dt, timeframe="5m")
```

1. Resolves credentials path from env var → config/credentials.yaml → .env
2. Checks cache — returns if it covers the requested range
3. Connects `RithmicHistoryApi` (standalone; falls back to shared loop with OrderApi)
4. Calls `download_historical_tick_data(symbol, exchange, start, end, bar_type_period)`
5. Normalizes columns (Open→open, etc.)
6. Caches to CSV and returns DataFrame

**Native bar periods:** 1, 3, 5, 8, 10, 15, 20, 30 minutes.
For 1h: downloads 30m bars and resamples OHLCV.

### In the Streamlit UI

Select **"Real Data (Rithmic)"** in the Data Source dropdown, then run the backtest.
The provider is imported lazily — if `pyrithmic` isn't installed the UI shows a warning.

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
py -3.10 -m pytest tests/ -v
```

5 tests cover: MA crossover, RSI, Breakout, equity curve length, and trade P&L types.
All must pass before committing. Tests use synthetic data (seed=99) — no Rithmic account needed.

---

## Known Constraints

- **No pandas-ta** — not compatible with Python 3.10. All indicators computed inline.
- **No live Rithmic connection** — `RithmicBroker` raises `NotImplementedError` until wired.
- **Single-symbol backtests** — the engine runs one symbol at a time.
