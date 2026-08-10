# Sample Market Data

Committed slices of **real 1-minute OHLCV history** — enough to run the platform
end to end and watch the analysis engine work on genuine market structure
instead of synthetic noise.

| File | Instrument | Bars | Period |
|---|---|---:|---|
| `ES_FULL.csv` | E-mini S&P 500 futures | 5,000 | 2025-01-01 → 2025-01-07 |
| `GC_FULL.csv` | Gold futures | 5,000 | 2025-06-22 → 2025-06-26 |
| `BTC_FULL.csv` | Bitcoin | 1,615 | 2025-10-20 → 2025-11-03 |
| `FULL_NVDA.csv` | NVIDIA | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_TSLA.csv` | Tesla | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_AAPL.csv` | Apple | 5,000 | 2025-01-02 → 2025-01-10 |

Total ≈ 1.6 MB.

## Using them

[`ExternalCSVProvider`](../../src/data/external_csv_provider.py) reads this
directory directly:

```python
from datetime import datetime
from src.data.external_csv_provider import ExternalCSVProvider

provider = ExternalCSVProvider(data_dir="data/sample")
df = provider.load("ES", datetime(2025, 1, 1), datetime(2025, 1, 8), "1m")
```

Or point every run at it by editing [`config/settings.yaml`](../../config/settings.yaml):

```yaml
data:
  external_dir: "data/sample"
```

## Format

```csv
Datetime,Open,High,Low,Close,Volume
2025-01-01 18:01:00,5949.25,5949.75,5943.25,5945.5,1369
```

- One row per **1-minute** bar, chronologically ascending
- `Datetime` is naive exchange-local time, `YYYY-MM-DD HH:MM:SS`
- Higher timeframes are **resampled from these 1-minute bars** by the provider —
  no separate file per timeframe. `load("ES", ..., "1h")` returns 87 bars from
  the 5,000 above.

> The `_FULL` / `FULL_` filenames are not cosmetic — `ExternalCSVProvider`
> resolves symbols by exactly these patterns. Renaming a file makes it
> invisible to the loader.

## Scope

Deliberately short slices, not the archive. The complete multi-year history runs
to hundreds of megabytes per instrument and stays out of version control — point
`external_dir` at a local archive to use it.

For runs needing no files at all,
[`sample_data.py`](../../src/data/sample_data.py) generates seeded GBM series
with regime shifts. That is what the test suite uses, and it is deterministic.
