"""Bollinger Bands (20, 2), against values computed by hand."""
import numpy as np
import pandas as pd
import pytest
from src.analysis.indicators import calc_bollinger_bands


def test_the_middle_band_is_a_simple_moving_average():
    close = pd.Series([float(i) for i in range(1, 31)])
    mid, _, _ = calc_bollinger_bands(close, length=20)
    # The 20th bar's window is 1..20, whose mean is 10.5.
    assert mid.iloc[19] == pytest.approx(10.5)


def test_the_bands_use_the_POPULATION_deviation_not_the_sample_one():
    """pandas defaults to ddof=1. Bollinger, and every platform that draws
    these, uses ddof=0 -- about 2.6% narrower on a 20-bar window."""
    close = pd.Series([float(i) for i in range(1, 21)])
    mid, up, lo = calc_bollinger_bands(close, length=20, num_dev=2.0)
    sigma_pop = float(np.std(np.arange(1, 21, dtype=float)))  # ddof=0
    assert up.iloc[19] == pytest.approx(10.5 + 2 * sigma_pop)
    assert lo.iloc[19] == pytest.approx(10.5 - 2 * sigma_pop)
    assert up.iloc[19] != pytest.approx(10.5 + 2 * close.rolling(20).std().iloc[19])


def test_a_flat_series_has_no_width():
    close = pd.Series([100.0] * 25)
    mid, up, lo = calc_bollinger_bands(close, length=20)
    assert mid.iloc[-1] == pytest.approx(100.0)
    assert up.iloc[-1] == pytest.approx(100.0)
    assert lo.iloc[-1] == pytest.approx(100.0)


def test_bars_before_a_full_window_are_nan_not_a_partial_average():
    close = pd.Series([float(i) for i in range(1, 31)])
    mid, up, lo = calc_bollinger_bands(close, length=20)
    assert mid.iloc[:19].isna().all()
    assert up.iloc[:19].isna().all()
    assert lo.iloc[:19].isna().all()
    assert mid.iloc[19:].notna().all()


def test_num_dev_scales_the_width_linearly():
    close = pd.Series(np.random.default_rng(7).normal(100, 3, 60))
    mid, up2, lo2 = calc_bollinger_bands(close, 20, 2.0)
    _, up1, lo1 = calc_bollinger_bands(close, 20, 1.0)
    assert (up2 - mid).iloc[-1] == pytest.approx(2 * (up1 - mid).iloc[-1])
    assert (mid - lo2).iloc[-1] == pytest.approx(2 * (mid - lo1).iloc[-1])


def test_the_bands_straddle_the_middle():
    close = pd.Series(np.random.default_rng(3).normal(4500, 8, 80))
    mid, up, lo = calc_bollinger_bands(close, 20, 2.0)
    tail = slice(19, None)
    assert (up[tail] >= mid[tail]).all()
    assert (lo[tail] <= mid[tail]).all()


def test_a_nonsense_length_is_refused():
    with pytest.raises(ValueError):
        calc_bollinger_bands(pd.Series([1.0, 2.0]), length=0)
