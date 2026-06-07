"""
Generate synthetic historical data for all configured symbols.

Run from project root:
    python scripts/generate_data.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from src.data.sample_data import generate_sample_data

CONFIGS = [
    dict(symbol="ES",  timeframe_minutes=5,  base_price=4500.0,  tick_size=0.25, bars=3000),
    dict(symbol="NQ",  timeframe_minutes=5,  base_price=15000.0, tick_size=0.25, bars=3000),
    dict(symbol="MES", timeframe_minutes=5,  base_price=4500.0,  tick_size=0.25, bars=3000),
    dict(symbol="CL",  timeframe_minutes=5,  base_price=75.0,    tick_size=0.01, bars=3000),
]

if __name__ == "__main__":
    start = datetime(2024, 1, 2, 9, 30)
    for cfg in CONFIGS:
        symbol = cfg.pop("symbol")
        tf = cfg.pop("timeframe_minutes")
        df = generate_sample_data(
            symbol=symbol,
            start=start,
            timeframe_minutes=tf,
            save_dir="data/historical",
            **cfg,
        )
        print(f"Generated {len(df)} bars for {symbol}_{tf}m  ->  data/historical/{symbol}_{tf}m.csv")
