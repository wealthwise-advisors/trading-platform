# 🚀 `scripts`

**Command-line entry points and the local launcher.**

[`run-autotrader.cmd`](run-autotrader.cmd) is the one to know on Windows: it frees
ports 8000 and 5173, starts the API and the web server in their own windows, and pins
Python 3.12 — 3.14 breaks `pandas_ta` and produces a test failure that looks real but
is not.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`run_backtest.py`](run_backtest.py) | Quick CLI backtest runner. | 109 |
| [`download_rithmic_data.py`](download_rithmic_data.py) | CLI script to download historical data from Rithmic and cache it locally. | 70 |
| [`run-autotrader.cmd`](run-autotrader.cmd) | Start AutoTrader locally: FastAPI on :8000, Vite on :5173. | 45 |
| [`generate_data.py`](generate_data.py) | Generate synthetic historical data for all configured symbols. | 34 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
