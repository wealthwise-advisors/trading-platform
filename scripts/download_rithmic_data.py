"""
CLI script to download historical data from Rithmic and cache it locally.

Requires pyrithmic:  pip install -r requirements.txt

Credentials are read from (in priority order):
  1. RITHMIC_CREDENTIALS_PATH environment variable
  2. .env file:            RITHMIC_CREDENTIALS_PATH=/path/to/credentials
  3. config/credentials.yaml:  rithmic.credentials_path: /path/to/credentials

Usage:
    python scripts/download_rithmic_data.py --symbol ES --timeframe 5m \\
        --start 2024-01-01 --end 2024-12-31
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime

from src.data.rithmic_provider import RithmicDataProvider, EXCHANGE_MAP


def parse_args():
    p = argparse.ArgumentParser(description="Download Rithmic historical bars")
    p.add_argument("--symbol",    required=True, help="e.g. ES, NQ, CL")
    p.add_argument("--timeframe", default="5m",  help="Bar period: 1m 3m 5m 8m 10m 15m 20m 30m 1h")
    p.add_argument("--start",     required=True, help="YYYY-MM-DD  (market open = 09:30 ET)")
    p.add_argument("--end",       required=True, help="YYYY-MM-DD  (market close = 16:00 ET)")
    p.add_argument("--start-time", default="09:30:00", dest="start_time",
                   help="Start time in HH:MM:SS (default 09:30:00 ET)")
    p.add_argument("--end-time",   default="16:00:00", dest="end_time",
                   help="End time HH:MM:SS for last day (default 16:00:00 ET)")
    p.add_argument("--exchange",  default=None,  help="Override exchange (default: auto from symbol)")
    p.add_argument("--cache-dir", default="data/historical", dest="cache_dir")
    p.add_argument("--force",     action="store_true", help="Re-download even if cache exists")
    return p.parse_args()


def main():
    args = parse_args()

    start_dt = datetime.strptime(f"{args.start} {args.start_time}", "%Y-%m-%d %H:%M:%S")
    end_dt   = datetime.strptime(f"{args.end} {args.end_time}",   "%Y-%m-%d %H:%M:%S")

    exchange = args.exchange or EXCHANGE_MAP.get(args.symbol.upper(), "CME")
    print(f"Downloading {args.symbol} ({exchange}) {args.timeframe} bars")
    print(f"  Range : {start_dt} → {end_dt}")
    print(f"  Cache : {args.cache_dir}/{args.symbol}_{args.timeframe}.csv")

    provider = RithmicDataProvider(cache_dir=args.cache_dir)
    df = provider.load(
        symbol=args.symbol.upper(),
        start=start_dt,
        end=end_dt,
        timeframe=args.timeframe,
        exchange=exchange,
        force_download=args.force,
    )

    print(f"\nDone — {len(df)} bars downloaded")
    print(f"  From : {df.index.min()}")
    print(f"  To   : {df.index.max()}")
    print(df.tail(5))


if __name__ == "__main__":
    main()
