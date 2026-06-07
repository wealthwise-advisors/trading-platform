# AutoTrader

A Python futures auto-trading platform with backtesting, bar-by-bar replay, and live Rithmic integration.

**Supported instruments:** ES, NQ, MES, MNQ, CL, GC, and more  
**Broker:** Rithmic (R|API+)  
**UI:** Streamlit + Plotly

---

## Quick Start

### 1. Prerequisites

- Python 3.10
- Git

### 2. Clone and install

```bash
git clone <repo-url>
cd Trading
pip install -r requirements.txt
```

### 3. Run with synthetic data (no Rithmic account needed)

```bash
python -m streamlit run ui/app.py
```

Open http://localhost:8501, select **Synthetic Data**, configure your strategy, and click **Run Backtest**.

---

## Rithmic Real Data Setup

To backtest on real market data you need a Rithmic account and credentials.

### Step 1 — Create your credentials file

Copy the template and fill in your path:

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Edit `config/credentials.yaml`:

```yaml
rithmic:
  credentials_path: "/path/to/your/rithmic/credentials"
```

The `credentials_path` must point to a directory containing a `RITHMIC_LIVE.ini` file with your Rithmic login details.

### Step 2 — Alternative: environment variable

Instead of editing `credentials.yaml`, you can set an environment variable:

**Windows (PowerShell):**
```powershell
$env:RITHMIC_CREDENTIALS_PATH = "C:\path\to\rithmic\credentials"
```

**Windows (permanent, via System Properties):**
Add `RITHMIC_CREDENTIALS_PATH` as a system/user variable.

**macOS / Linux:**
```bash
export RITHMIC_CREDENTIALS_PATH=/path/to/rithmic/credentials
```

Or add it to a `.env` file in the project root:
```
RITHMIC_CREDENTIALS_PATH=/path/to/rithmic/credentials
```

### Step 3 — Run the app

```bash
python -m streamlit run ui/app.py
```

Select **Real Data (Rithmic)** in the Data Source dropdown, pick a symbol and date range, and click **Run Backtest**.

### Download data via CLI

```bash
python scripts/download_rithmic_data.py --symbol ES --timeframe 5m \
    --start 2024-01-01 --end 2024-12-31
```

Optional flags: `--force` (re-download), `--exchange CME`

---

## Project Structure

```
Trading/
├── config/
│   ├── settings.yaml              # Contract specs, capital defaults
│   ├── credentials.yaml           # Your local credentials (gitignored)
│   └── credentials.yaml.example   # Template — copy and fill in
│
├── src/
│   ├── data/
│   │   ├── rithmic_provider.py    # Download real bars from Rithmic
│   │   ├── csv_provider.py        # Load OHLCV from local CSV
│   │   └── sample_data.py         # Synthetic data generator
│   ├── strategies/                # MA Crossover, RSI, Breakout
│   ├── backtesting/               # BacktestEngine, ReplayEngine
│   └── broker/                    # PaperBroker, RithmicBroker (stub)
│
├── ui/
│   ├── app.py                     # Backtest dashboard  (port 8501)
│   ├── live_app.py                # Bar-by-bar replay   (port 8502)
│   └── report.py                  # HTML report export
│
├── scripts/
│   ├── run_backtest.py            # CLI backtest
│   ├── generate_data.py           # Generate synthetic CSV data
│   └── download_rithmic_data.py   # Download Rithmic historical bars
│
└── tests/
    └── test_engine.py             # 5 smoke tests
```

---

## Running the Apps

```bash
# Backtest dashboard (port 8501)
python -m streamlit run ui/app.py

# Bar-by-bar live replay (port 8502)
python -m streamlit run ui/live_app.py --server.port 8502

# CLI backtest (no UI)
python scripts/run_backtest.py --symbol ES --strategy ma --fast 9 --slow 21

# Generate synthetic test data
python scripts/generate_data.py
```

---

## Writing a Strategy

1. Create a new file in `src/strategies/`
2. Subclass `BaseStrategy` and implement `on_bar()`
3. Register it in `src/strategies/__init__.py`
4. Add to the sidebar dropdown in `ui/app.py` and `ui/live_app.py`

```python
from src.strategies.base_strategy import BaseStrategy, Signal, SignalType

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MyStrategy")

    def reset(self):
        pass

    def on_bar(self, bars_df, current_bar, position):
        if len(bars_df) < 20:
            return None
        # your logic here
        return Signal(
            signal_type=SignalType.BUY,
            strategy_name=self.name,
            timestamp=current_bar.timestamp,
            price=current_bar.close,
            reason="Your reason",
        )
```

---

## Sharing Backtest Results

Click **Export Report (HTML)** in the dashboard. The output is a single self-contained `.html` file (~185 KB) that can be opened in any browser — no Python or server needed. Share via email, Slack, or Google Drive.

---

## Tests

```bash
python -m pytest tests/ -v
```

All 5 tests use synthetic data (deterministic seed) — no Rithmic account required.

---

## Exchange Codes (Rithmic)

| Symbol | Exchange |
|--------|----------|
| ES, NQ, MES, MNQ | CME |
| CL, NG, MCL | NYMEX |
| GC, SI, MGC | COMEX |
| ZN, ZB, ZF, YM | CBOT |

---

## Notes

- `pandas-ta` is **not** used — incompatible with Python 3.10. All indicators (EMA, RSI, ATR) are computed inline with pandas/numpy.
- `config/credentials.yaml` and `.env` are gitignored — never commit credentials.
- `data/historical/` is gitignored — each developer downloads their own data.
