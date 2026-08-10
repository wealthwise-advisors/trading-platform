"""Driver script: fetch real market data and populate the validation
database (Task 8). Reuses already-fetched real caches where available
(ES/NQ/SPY, from earlier sessions' Schwab pulls) and fetches fresh for
Gold/Crude Oil. Run standalone: `py -3.12 validation/populate.py`
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import time

import pandas as pd

from validation.db import init_db, connect
from validation.pipeline import populate_market_timeframe, CHARTS_DIR, TIMEFRAMES

SCRATCH = Path(r"C:\Users\ASUS\AppData\Local\Temp\claude\d--wealthwise-advisors\6957ec8d-f0e8-437f-85ab-101cef42d59c\scratchpad")

# Window sizes per timeframe -- enough bars for the engine to find real
# structure (matches what worked well throughout this whole session's
# real-data verification), scaled down for coarser timeframes where fewer
# bars are available in total.
WINDOW_BARS = {"5m": 300, "15m": 300, "1h": 250, "4h": 150, "1d": 60}

REUSABLE_CACHE = {
    ("ES", "5m"): "es_5m_cache.csv", ("ES", "15m"): "es_15m_cache.csv",
    ("ES", "1h"): "es_1h_cache.csv", ("ES", "4h"): "es_4h_cache.csv", ("ES", "1d"): "es_1d_cache.csv",
    ("NQ", "5m"): "nq_5m_cache.csv", ("NQ", "15m"): "nq_15m_cache.csv",
    ("NQ", "1h"): "nq_1h_cache.csv", ("NQ", "4h"): "nq_4h_cache.csv", ("NQ", "1d"): "nq_1d_cache.csv",
    ("SPY", "5m"): "spy_5m_cache.csv", ("SPY", "15m"): "spy_15m_cache.csv",
    ("SPY", "1h"): "spy_1h_cache.csv", ("SPY", "4h"): "spy_4h_cache.csv", ("SPY", "1d"): "spy_1d_cache.csv",
}

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _load_or_fetch(market: str, timeframe: str, provider) -> tuple:
    """Returns (df, data_source). Reuses a cached CSV if one exists;
    otherwise fetches fresh via Schwab (native tf) or resamples from a
    freshly-fetched 1h series (4h/1d)."""
    cached = REUSABLE_CACHE.get((market, timeframe))
    if cached and (SCRATCH / cached).exists():
        df = pd.read_csv(SCRATCH / cached)
        df.columns = [c.lower() for c in df.columns]
        return df, "schwab_real_cached"

    end = datetime.datetime.now()
    if timeframe in ("5m", "15m", "1h"):
        days = {"5m": 45, "15m": 90, "1h": 365}[timeframe]
        df = provider.load(market, end - datetime.timedelta(days=days), end, timeframe=timeframe)
        df.columns = [c.lower() for c in df.columns]
        return df.reset_index(drop=True), "schwab_real"
    else:
        # 4h / 1d: resample from a fresh 1h fetch (same method the provider
        # itself uses for its own 1h-from-30m resampling). The provider
        # already returns a DatetimeIndex named "timestamp" -- no
        # reconstruction needed.
        df1h = provider.load(market, end - datetime.timedelta(days=365), end, timeframe="1h")
        df1h.columns = [c.lower() for c in df1h.columns]
        rule = {"4h": "4h", "1d": "1D"}[timeframe]
        out = df1h.resample(rule).agg(AGG).dropna(how="any")
        out = out[out["volume"] > 0].reset_index(drop=True)
        return out, "schwab_real_resampled"


def main():
    init_db()
    from src.data.schwab_provider import SchwabDataProvider
    provider = SchwabDataProvider()

    summary = []
    with connect() as conn:
        for market in ["ES", "NQ", "SPY", "GC", "CL"]:
            for timeframe in TIMEFRAMES:
                t0 = time.time()
                try:
                    df, source = _load_or_fetch(market, timeframe, provider)
                except Exception as exc:
                    summary.append((market, timeframe, 0, f"FETCH FAILED: {exc}"))
                    continue
                if len(df) < 30:
                    summary.append((market, timeframe, 0, "too few bars"))
                    continue

                csv_path = CHARTS_DIR / f"{market.lower()}_{timeframe}.csv"
                df.to_csv(csv_path, index=False)

                n = populate_market_timeframe(
                    conn, market, timeframe, df, WINDOW_BARS[timeframe], source,
                    price_csv_path=str(csv_path),
                )
                summary.append((market, timeframe, n, f"{source}, {len(df)} bars, {time.time()-t0:.1f}s"))
                print(f"{market:5} {timeframe:4} -> {n:3} charts populated  ({summary[-1][3]})")

    total = sum(s[2] for s in summary)
    print(f"\nTOTAL charts populated: {total}")
    return summary


if __name__ == "__main__":
    main()
