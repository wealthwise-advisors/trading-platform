"""Independent Industry Benchmark -- objective market-regime classification
(Task 9 Improvement, requirement 1: "multiple market regimes ... bull ...
bear ... sideways ... high-volatility ... low-volatility").

Both labels are computed directly and objectively from the chart's own
OHLC data -- never asserted or hand-picked -- so every regime label in
`benchmark_charts` is reproducible from `price_csv_path` alone.

Trend regime uses a self-contained statistic (no external population
needed): a drift-vs-noise z-score. This is the standard way to ask
"is this move bigger than what randomness alone would produce at this
chart's own realized volatility" -- a real trend should look large
relative to the noise, not just have a positive sign.

Volatility regime is inherently RELATIVE (there is no universal absolute
threshold that means the same thing for 5m ES bars and 1d GC bars), so it
is computed relative to the realized volatility of the other charts
in the same (market, timeframe) group -- median split, not asserted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Empirically-neutral convention, not tuned to this dataset: a drift whose
# magnitude is less than 1 standard deviation of what pure random-walk
# noise at this chart's own realized per-bar volatility would produce is
# "sideways" -- indistinguishable from noise. Beyond that, sign gives the
# direction. This is the standard drift/noise ratio (a t-stat-like
# quantity), not a curve-fit threshold.
_TREND_Z_THRESHOLD = 1.0


def trend_stats(df: pd.DataFrame) -> dict:
    close = df["close"].to_numpy(dtype=float)
    log_ret = np.diff(np.log(close))
    n = len(log_ret)
    total_return = float(np.log(close[-1] / close[0]))
    per_bar_vol = float(np.std(log_ret, ddof=1)) if n > 1 else 0.0
    # Expected noise-only spread of a total return over n steps of a
    # zero-drift random walk with this per-bar vol.
    expected_noise_spread = per_bar_vol * np.sqrt(n) if n > 0 else 0.0
    z = total_return / expected_noise_spread if expected_noise_spread > 1e-12 else 0.0
    return {
        "total_log_return": round(total_return, 6),
        "per_bar_vol": round(per_bar_vol, 6),
        "trend_z": round(float(z), 4),
        "n_bars": n,
    }


def classify_trend(df: pd.DataFrame) -> tuple[str, dict]:
    stats = trend_stats(df)
    z = stats["trend_z"]
    if z >= _TREND_Z_THRESHOLD:
        trend = "bull"
    elif z <= -_TREND_Z_THRESHOLD:
        trend = "bear"
    else:
        trend = "sideways"
    return trend, stats


def realized_vol(df: pd.DataFrame) -> float:
    close = df["close"].to_numpy(dtype=float)
    log_ret = np.diff(np.log(close))
    return float(np.std(log_ret, ddof=1)) if len(log_ret) > 1 else 0.0


def classify_volatility_group(vols_by_key: dict[str, list[float]]) -> dict[str, float]:
    """vols_by_key: {(market,timeframe) group key -> [realized_vol per chart]}.
    Returns {group_key: median_vol} for use as each group's own split point."""
    return {k: float(np.median(v)) for k, v in vols_by_key.items()}


def classify_volatility(vol: float, group_median: float) -> str:
    return "high_vol" if vol >= group_median else "low_vol"
