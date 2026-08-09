"""Shared fixtures for the Elliott Wave suite.

Most rule tests build `Pivot` objects DIRECTLY rather than going through the
detector. That is deliberate: a gate test should pin down the gate's boundary,
not the detector's tuning. Detector behaviour has its own module.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.analysis.elliott_wave.models import Pivot, PivotKind  # noqa: E402

T0 = datetime(2024, 1, 2, 9, 30)


def pv(index: int, price: float, kind: PivotKind, scale: int = 1) -> Pivot:
    """A pivot with a confirmation bar one step later (the minimum legal gap)."""
    return Pivot(index=index, confirm_index=index + 1,
                 timestamp=T0 + timedelta(minutes=5 * index),
                 price=float(price), kind=kind, scale=scale)


H = PivotKind.HIGH
L = PivotKind.LOW


def up_impulse(p0=100, p1=140, p2=120, p3=200, p4=170, p5=230, scale=1):
    """A textbook up-impulse: L,H,L,H,L,H.

    Defaults satisfy every implementable gate:
      IMP-03  wave 2 ends at 120 > start 100
      IMP-04  len3=80 > min(len1=40, len5=60)
      IMP-05  wave 1 territory [100,140]; wave 4 [170,200] -- disjoint
    """
    prices = [p0, p1, p2, p3, p4, p5]
    kinds = [L, H, L, H, L, H]
    return [pv(i * 10, prices[i], kinds[i], scale) for i in range(6)]


def down_impulse(p0=230, p1=190, p2=210, p3=130, p4=160, p5=100, scale=1):
    """Mirror image of up_impulse: H,L,H,L,H,L."""
    prices = [p0, p1, p2, p3, p4, p5]
    kinds = [H, L, H, L, H, L]
    return [pv(i * 10, prices[i], kinds[i], scale) for i in range(6)]


def correction(p0=200, p1=150, p2=180, p3=130, scale=1):
    """A 3-leg down correction: H,L,H,L (waves A, B, C)."""
    prices = [p0, p1, p2, p3]
    kinds = [H, L, H, L]
    return [pv(i * 10, prices[i], kinds[i], scale) for i in range(4)]


def bars_from_path(points, bars_per_leg=6, start=T0):
    """Build an OHLCV frame that traces a piecewise-linear price path.

    `points` is a list of prices. Highs/lows hug the path tightly so the
    directional-change detector sees clean turns and nothing spurious.
    """
    closes, times = [], []
    t = start
    for a, b in zip(points, points[1:]):
        for k in range(bars_per_leg):
            closes.append(a + (b - a) * (k / bars_per_leg))
            times.append(t)
            t += timedelta(minutes=5)
    closes.append(points[-1])
    times.append(t)
    # Plain lists, NOT a pd.Series: a Series carries its own RangeIndex and
    # would be re-aligned against the DatetimeIndex below, silently producing
    # an all-NaN frame.
    return pd.DataFrame(
        {
            "open": list(closes),
            "high": [c * 1.0002 for c in closes],
            "low": [c * 0.9998 for c in closes],
            "close": list(closes),
            "volume": [100] * len(closes),
        },
        index=pd.DatetimeIndex(times, name="timestamp"),
    )


@pytest.fixture
def zigzag_bars():
    """A long alternating path, rich enough to yield multi-scale pivots."""
    pts, price, step = [1000.0], 1000.0, 1.0
    for i in range(60):
        step = -step
        price += step * (12 + (i % 5) * 4)
        pts.append(price)
    return bars_from_path(pts, bars_per_leg=5)


@pytest.fixture
def reference_df():
    """Deterministic synthetic data -- same generator the existing suite uses."""
    from src.data.sample_data import generate_sample_data
    return generate_sample_data(symbol="ESEW", start=T0, bars=1200,
                                timeframe_minutes=5, base_price=4500.0,
                                tick_size=0.25, seed=42, save_dir=None)


@pytest.fixture
def flat_rsi():
    """A never-NaN RSI that never diverges.

    Useful for asserting IMP-06 FAILS. Note a constant series means
    ``r5 < r3`` is false, so an up-impulse is rejected -- that is the point.
    """
    def _make(n, value=50.0):
        return pd.Series([value] * n)
    return _make


@pytest.fixture
def diverging_rsi():
    """A monotonically falling RSI, never NaN.

    Any later bar reads lower than any earlier one, so an up-impulse whose
    wave 5 exceeds wave 3 always shows divergence and IMP-06 passes. This is
    the fixture to use when a test wants a candidate to survive every gate.
    """
    def _make(n=400, hi=95.0, lo=5.0):
        return pd.Series([hi - (hi - lo) * i / max(1, n - 1) for i in range(n)])
    return _make
