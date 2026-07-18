"""Shared fixtures and helpers for the Elliott Wave regression suite (Task 7).

Every test file under tests/elliott/ imports from here rather than
redefining its own swing/DataFrame builders -- one canonical way to
construct synthetic Elliott structures, reused across impulse/correction/
triangle/complex-correction/diagonal/regression/performance/determinism/API
tests, so a bug in a builder gets caught everywhere at once instead of
silently diverging per file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

from src.analysis.swing_identification import Swing, SwingType

H = SwingType.HIGH
L = SwingType.LOW


def mk_swing(idx: int, price: float, kind: SwingType, confirm_offset: int = 2) -> Swing:
    """Canonical synthetic swing builder -- same (idx, idx+2) confirm-gap
    convention already used throughout src/analysis/*.py's own __main__
    demos, so hand-built test sequences look and behave like the reference
    examples the production code was itself validated against."""
    return Swing(idx, idx + confirm_offset, price, kind)


def swings_from_pivots(pivots: list, start_idx: int = 0, gap: int = 2) -> list:
    """Build an alternating H/L swing list from a plain list of
    (price, kind) tuples, spacing indices by `gap` bars apart -- the most
    common way test cases specify a structure ("here are the pivot prices
    and whether each is a high or low")."""
    out = []
    idx = start_idx
    for price, kind in pivots:
        out.append(mk_swing(idx, price, kind))
        idx += gap
    return out


def ohlc_from_pivots(pivot_prices: list, bars_per_leg: int = 8,
                     noise: float = 0.15, seed: int = 7) -> pd.DataFrame:
    """Build a synthetic OHLC DataFrame that interpolates between the given
    price levels (a plain list of floats, alternating direction implied by
    up/down moves) -- mirrors wave_numbering.py's own __main__ demo helper
    (_ohlc_from_pivots). Used wherever a test needs REAL bar-level data
    (recursive verification, analyze(), the API layer), not just an
    abstract Swing list -- identify_swings() re-derives a clean swing
    sequence from the interpolated closes.
    """
    rng = np.random.default_rng(seed)
    closes = []
    for a, b in zip(pivot_prices, pivot_prices[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivot_prices[-1])
    closes = np.asarray(closes, dtype=float) + rng.normal(0, noise, len(closes))
    high = closes + rng.uniform(0.05, 0.3, len(closes))
    low = closes - rng.uniform(0.05, 0.3, len(closes))
    open_ = np.roll(closes, 1)
    open_[0] = closes[0]
    volume = np.full(len(closes), 100.0)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": closes, "volume": volume})


def assert_deterministic(fn, *args, runs: int = 3, **kwargs):
    """Call fn(*args, **kwargs) `runs` times and assert every call produces
    an identical (==-equal) result. Used throughout the suite for
    requirement 2's "deterministic output" per-case checks and requirement
    5's dedicated determinism tests. Returns the common result so callers
    can keep asserting on it without a redundant extra call."""
    results = [fn(*args, **kwargs) for _ in range(runs)]
    first = results[0]
    for k, r in enumerate(results[1:], start=2):
        assert r == first, f"non-deterministic: run 1 != run {k}\n  run1={first!r}\n  run{k}={r!r}"
    return first
