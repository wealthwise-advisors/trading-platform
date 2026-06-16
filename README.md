# AutoTrader

A Python futures auto-trading platform with backtesting, bar-by-bar replay, and live market data via Schwab or Rithmic.

**Supported instruments:** ES, NQ, MES, MNQ, CL, GC, and more  
**Data sources:** Charles Schwab API, Rithmic (R|API+), your own CSV files, or synthetic data  
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

## Schwab Live Data Setup

Schwab is the recommended data source for live and recent historical bars. It uses OAuth2 — no manual API key rotation needed for daily use, only a browser login every 7 days.

### Step 1 — Create a Schwab developer app

1. Go to [developer.schwab.com](https://developer.schwab.com) and log in with your Schwab account
2. Click **My Apps → Create App**
3. Set the **Callback URL** to `https://127.0.0.1`
4. Copy the **App Key** (32 chars) and **App Secret** (16 chars)

### Step 2 — Add credentials

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Edit `config/credentials.yaml`:

```yaml
schwab:
  app_key: "YOUR_32_CHAR_APP_KEY"
  app_secret: "YOUR_16_CHAR_SECRET"
  callback_url: "https://127.0.0.1"
  tokens_file: "config/schwab_tokens.json"
```

### Step 3 — Authenticate (first time)

Start the app and select **Live Data (Schwab)** in the sidebar. A widget appears:

1. Click the authorization link — your browser opens the Schwab login page
2. Log in and approve the app
3. Copy the full URL from the browser address bar (it starts with `https://127.0.0.1?code=...`)
4. Paste it into the **"Paste redirect URL"** box and click **Submit & Save Tokens**

The app writes `config/schwab_tokens.json` (gitignored) and shows **"Schwab connected"**.

### Step 4 — Run a backtest

Select **Live Data (Schwab)**, choose a symbol (type any futures root like `NQ`, `GC`, `CL` in the **Other…** field if not in the dropdown), set a date range, and click **Run Backtest**.

> **Supported timeframes:** 1m, 5m, 10m, 15m, 30m, 1h  
> **Futures symbol mapping:** `ES` → `/ES`, `NQ` → `/NQ`, etc. (automatic)  
> **Data limit:** Up to ~47 days of 1-minute bars per request; longer ranges are chunked automatically.

### Token refresh (every 7 days)

The **access token** (30 min) refreshes automatically in the background — no action needed.

The **refresh token** lasts **7 days**. The sidebar shows a warning 24 hours before it expires. When it does:

1. The sidebar widget re-appears automatically
2. Click the auth link, approve, paste the redirect URL
3. Done — no credentials need to change

### Moving to a new computer

Copy these two files from your existing machine:

| File | Purpose |
|------|---------|
| `config/credentials.yaml` | App key + secret |
| `config/schwab_tokens.json` | Active OAuth2 tokens |

Alternatively, just copy `credentials.yaml` and re-authenticate (Step 3) to generate a fresh `schwab_tokens.json`.

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
│   │   ├── schwab_provider.py     # Schwab market data (price_history API)
│   │   ├── schwabdev/             # Schwab API client library
│   │   ├── external_csv_provider.py # Load your own CSV files (C:\Data)
│   │   ├── rithmic_provider.py    # Download real bars from Rithmic
│   │   ├── csv_provider.py        # Load OHLCV from local CSV
│   │   └── sample_data.py         # Synthetic data generator
│   ├── strategies/                # MA Crossover, RSI, Breakout, RSI Divergence
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
- `config/credentials.yaml`, `config/schwab_tokens.json`, and `.env` are gitignored — never commit credentials or tokens.
- `data/historical/` is gitignored — each developer downloads their own data.
- On Windows use `py -3.10` instead of `python` to ensure the correct interpreter is used.
