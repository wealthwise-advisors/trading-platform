# Sample Market Data

Committed slices of **real 1-minute OHLCV history** across every instrument in
the research archive — enough to run the platform end to end and see the
analysis engine work on genuine market structure.

**16 files · 5,000 bars each · ~4.2 MB total**

## Futures

| File | Instrument | Bars | Period |
|---|---|---:|---|
| `ES_FULL.csv` | E-mini S&P 500 | 5,000 | 2008-01-02 → 2008-01-08 |
| `ES_FULL_2022.csv` | E-mini S&P 500 | 5,000 | 2022-01-02 → 2022-01-06 |
| `ES_FULL_2023.csv` | E-mini S&P 500 | 5,000 | 2023-01-02 → 2023-01-06 |
| `ES_FULL_2024.csv` | E-mini S&P 500 | 5,000 | 2024-01-01 → 2024-01-05 |
| `ES_FULL_2025.csv` | E-mini S&P 500 | 5,000 | 2025-01-01 → 2025-01-07 |
| `GC_FULL.csv` | Gold | 5,000 | 2025-06-22 → 2025-06-26 |

## Equities

| File | Instrument | Bars | Period |
|---|---|---:|---|
| `FULL_AAPL.csv` | Apple | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_AMD.csv` | AMD | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_COIN.csv` | Coinbase | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_CRWV.csv` | CoreWeave | 5,000 | 2025-04-01 → 2025-04-08 |
| `FULL_META.csv` | Meta | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_NVDA.csv` | NVIDIA | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_SMCI.csv` | Super Micro | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_TSLA.csv` | Tesla | 5,000 | 2025-01-02 → 2025-01-10 |
| `FULL_UPST.csv` | Upstart | 5,000 | 2025-01-02 → 2025-01-14 |

## Crypto

| File | Instrument | Bars | Period |
|---|---|---:|---|
| `BTC_FULL.csv` | Bitcoin | 1,615 | 2025-10-20 → 2025-11-03 |

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

**Year-file resolution.** When a symbol has per-year files, the provider prefers
those over the monolithic one — asking for `ES` across 2025 loads
`ES_FULL_2025.csv`, not the 2008 slice in `ES_FULL.csv`. Multi-year ranges are
concatenated.

## Format

```csv
Datetime,Open,High,Low,Close,Volume
2025-01-01 18:01:00,5949.25,5949.75,5943.25,5945.5,1369
```

- One row per **1-minute** bar, chronologically ascending
- `Datetime` is naive exchange-local time, `YYYY-MM-DD HH:MM:SS`
- Higher timeframes are **resampled from these 1-minute bars** by the provider —
  no separate file per timeframe

> The `_FULL` / `FULL_` filenames are not cosmetic — `ExternalCSVProvider`
> resolves symbols by exactly these patterns. Renaming a file makes it
> invisible to the loader.

## Scope

Deliberately short slices, not the archive. The complete multi-year history runs
to **433 MB** — one file alone is 335 MB, past GitHub's 100 MB per-file limit —
so it stays local. Point `external_dir` at your own archive to use it in full.

For runs needing no files at all,
[`sample_data.py`](../../src/data/sample_data.py) generates seeded GBM series
with regime shifts. That is what the test suite uses, and it is deterministic.
