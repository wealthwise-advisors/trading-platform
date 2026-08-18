# 📥 `src/data`

**Getting bars in — and aggregating them exactly one way.**

### Providers

| Source | Use |
|---|---|
| **Schwab** | Live and recent history. Intraday reaches back ~180 days |
| **CSV** | The historical archive, for anything older |
| **Synthetic** | Deterministic generated bars, for tests |

### The shared aggregator

[`resample.py`](resample.py) is the only place bars are aggregated. It is
session-anchored — bars tile from the exchange's bar anchor (01:00 for futures), not
from midnight and not from the session open, because those produce a grid no broker
platform uses.

It also carries `with_vwap_price`, so each output bar keeps its own volume-weighted
price built from the minutes inside it. Without that, VWAP collapses to `(H+L+C)/3`
and the same 30-minute bar reports a different value depending on which other
timeframes happen to be selected.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`schwab_provider.py`](schwab_provider.py) | SchwabDataProvider — historical OHLCV bars from Charles Schwab market data API. | 429 |
| [`rithmic_provider.py`](rithmic_provider.py) | RithmicDataProvider — downloads historical OHLCV bars via the Rithmic History API. | 267 |
| [`external_csv_provider.py`](external_csv_provider.py) | ExternalCSVProvider — load historical data from your own CSV files. | 261 |
| [`resample.py`](resample.py) | The one place OHLCV bars get aggregated up a timeframe. | 231 |
| [`sample_data.py`](sample_data.py) | Generate realistic synthetic OHLCV data for testing strategies without live data. | 80 |
| [`base_provider.py`](base_provider.py) | The interface every data provider satisfies, so the engine does not know its source. | 53 |
| [`csv_provider.py`](csv_provider.py) | Reads bars from the local CSV archive, for history older than a broker will serve. | 40 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`schwabdev/`](schwabdev) | 3 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
