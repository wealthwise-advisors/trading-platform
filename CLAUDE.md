# AutoTrader â€” Claude Context Guide

This document tells Claude everything it needs to know to work on this codebase
effectively. Read this before touching any code.

---

## What This Project Is

A **Python futures/options auto-trading platform** with three modes of operation:

| Mode | Entry point | Purpose |
|------|-------------|---------|
| Backtest (batch) | `ui/app.py` | Run full backtest, explore results, export HTML report |
| Live Replay | `ui/live_app.py` | Watch strategy trade bar-by-bar in real-time animation |
| Live Trading | `src/live/trader.py` | Connect to Rithmic and trade live (stub â€” not yet wired) |

**Asset class:** Futures (ES, NQ, MES, CL). Options support is planned but not implemented.  
**Broker:** Rithmic (R|API+). The live adapter is stubbed â€” backtesting uses `PaperBroker`.  
**UI:** Streamlit + Plotly.

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
# Backtest dashboard (port 8501)
py -3.12 -m streamlit run ui/app.py

# Live replay dashboard (port 8502)
py -3.12 -m streamlit run ui/live_app.py --server.port 8502

# CLI backtest (quick, no UI)
py -3.12 scripts/run_backtest.py --symbol ES --strategy ma --fast 9 --slow 21

# Generate synthetic data for all symbols
py -3.12 scripts/generate_data.py

# Tests
py -3.12 -m pytest tests/ -v
```

---

## Project Structure

```
Trading/
â”œâ”€â”€ config/
â”‚   â”œâ”€â”€ settings.yaml              # Contract specs, capital, log level
â”‚   â”œâ”€â”€ credentials.yaml           # Local credentials (gitignored â€” never commit)
â”‚   â””â”€â”€ credentials.yaml.example   # Committed template â€” copy and fill in
â”‚
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ config.py              # Loads settings.yaml + credentials.yaml
â”‚   â”‚
â”‚   â”œâ”€â”€ data/
â”‚   â”‚   â”œâ”€â”€ base_provider.py   # DataProvider ABC + Bar dataclass
â”‚   â”‚   â”œâ”€â”€ csv_provider.py    # Load OHLCV from CSV files
â”‚   â”‚   â”œâ”€â”€ rithmic_provider.py# Download real bars from Rithmic
â”‚   â”‚   â””â”€â”€ sample_data.py     # Synthetic data generator (GBM + regimes)
â”‚   â”‚
â”‚   â”œâ”€â”€ strategies/
â”‚   â”‚   â”œâ”€â”€ base_strategy.py   # BaseStrategy ABC, Signal, SignalType
â”‚   â”‚   â”œâ”€â”€ ma_crossover.py    # EMA crossover (fast/slow)
â”‚   â”‚   â”œâ”€â”€ rsi_mean_reversion.py  # RSI oversold/overbought mean reversion
â”‚   â”‚   â””â”€â”€ breakout.py        # Donchian channel breakout with ATR trailing stop
â”‚   â”‚
â”‚   â”œâ”€â”€ backtesting/
â”‚   â”‚   â”œâ”€â”€ engine.py          # BacktestEngine â€” runs all bars at once
â”‚   â”‚   â”œâ”€â”€ replay_engine.py   # ReplayEngine â€” step-by-step, drives live UI
â”‚   â”‚   â”œâ”€â”€ results.py         # BacktestResults + Trade dataclasses
â”‚   â”‚   â””â”€â”€ metrics.py         # compute_metrics() â€” Sharpe, Sortino, drawdown, etc.
â”‚   â”‚
â”‚   â”œâ”€â”€ broker/
â”‚   â”‚   â”œâ”€â”€ base_broker.py     # BaseBroker ABC, Order, Fill, OrderSide, OrderType
â”‚   â”‚   â”œâ”€â”€ paper_broker.py    # PaperBroker â€” simulated fills with slippage
â”‚   â”‚   â””â”€â”€ rithmic_broker.py  # RithmicBroker stub
â”‚   â”‚
â”‚   â””â”€â”€ live/
â”‚       â””â”€â”€ trader.py          # LiveTrader â€” main loop (stub until Rithmic is wired)
â”‚
â”œâ”€â”€ ui/
â”‚   â”œâ”€â”€ app.py                 # Static backtest dashboard
â”‚   â”œâ”€â”€ live_app.py            # Bar-by-bar replay dashboard
â”‚   â”œâ”€â”€ report.py              # HTML report generator (shareable, offline)
â”‚   â””â”€â”€ components/
â”‚       â”œâ”€â”€ charts.py          # Plotly chart builders (candlestick, equity, etc.)
â”‚       â””â”€â”€ metrics.py         # Streamlit metric card renderers
â”‚
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ run_backtest.py        # CLI backtest runner
â”‚   â”œâ”€â”€ generate_data.py       # Generate synthetic CSV data for all symbols
â”‚   â””â”€â”€ download_rithmic_data.py # Download real Rithmic bars
â”‚
â”œâ”€â”€ tests/
â”‚   â””â”€â”€ test_engine.py         # 5 smoke tests (all passing)
â”‚
â”œâ”€â”€ data/
â”‚   â””â”€â”€ historical/            # CSV files: {SYMBOL}_{timeframe}.csv  (gitignored)
â”‚
â””â”€â”€ reports/                   # Generated HTML reports (gitignored)
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

The engine handles position flipping automatically â€” you just emit BUY/SELL/CLOSE signals.

### PaperBroker fill model

Orders are filled on the **next bar's open** (realistic â€” no look-ahead):
- Market orders: filled at `bar.open Â± slippage_ticks * tick_size`
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

### In the Streamlit UI

Select **"Real Data (Rithmic)"** in the Data Source dropdown, then run the backtest.
The provider is imported lazily â€” if `pyrithmic` isn't installed the UI shows a warning.

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

5 tests cover: MA crossover, RSI, Breakout, equity curve length, and trade P&L types.
All must pass before committing. Tests use synthetic data (seed=99) â€” no Rithmic account needed.

---

## Known Constraints

- **pandas_ta** is available (Python 3.12). Use `import pandas_ta as ta` for indicators.
- **No live Rithmic connection** â€” `RithmicBroker` raises `NotImplementedError` until wired.
- **Single-symbol backtests** â€” the engine runs one symbol at a time.
