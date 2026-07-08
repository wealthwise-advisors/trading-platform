"""Generate realistic synthetic OHLCV data for testing strategies without live data."""

from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd


def generate_sample_data(
    symbol: str = "ES",
    start: datetime = None,
    bars: int = 2000,
    timeframe_minutes: int = 5,
    base_price: float = 4500.0,
    tick_size: float = 0.25,
    volatility: float = 0.0008,
    seed: int = 42,
    save_dir: str = "data/historical",
    tf_label: str = None,
) -> pd.DataFrame:
    """
    Generate synthetic futures OHLCV data using a geometric Brownian motion model
    with intraday volatility clustering and trend regimes.
    """
    np.random.seed(seed)
    if start is None:
        start = datetime(2024, 1, 2, 9, 30)

    # Build timestamps (skip weekends)
    timestamps = []
    current = start
    while len(timestamps) < bars:
        if current.weekday() < 5:  # Mon-Fri
            timestamps.append(current)
        current += timedelta(minutes=timeframe_minutes)

    n = len(timestamps)

    # GBM with trend regimes
    regime_length = 200
    returns = np.zeros(n)
    drift = 0.0
    for i in range(n):
        if i % regime_length == 0:
            drift = np.random.choice([-0.0002, 0.0, 0.0002, 0.0003])
        vol = volatility * (1 + 0.5 * np.abs(np.sin(i / 50)))  # vol clustering
        returns[i] = drift + vol * np.random.randn()

    closes = base_price * np.exp(np.cumsum(returns))
    closes = np.round(closes / tick_size) * tick_size

    # Build OHLCV from close series
    opens, highs, lows, volumes = [], [], [], []
    for i in range(n):
        o = closes[i - 1] if i > 0 else closes[0]
        bar_vol = volatility * 0.5 * np.abs(np.random.randn())
        h = max(o, closes[i]) + np.abs(np.random.randn()) * base_price * bar_vol
        l = min(o, closes[i]) - np.abs(np.random.randn()) * base_price * bar_vol
        h = np.round(h / tick_size) * tick_size
        l = np.round(l / tick_size) * tick_size
        opens.append(np.round(o / tick_size) * tick_size)
        highs.append(h)
        lows.append(l)
        volumes.append(int(np.random.exponential(500) + 100))

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=pd.DatetimeIndex(timestamps, name="timestamp"))

    if save_dir:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        label = tf_label or f"{timeframe_minutes}m"
        df.to_csv(path / f"{symbol}_{label}.csv", index_label="timestamp")

    return df
