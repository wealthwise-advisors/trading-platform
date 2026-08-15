"""
VWAP band regression tests.

Two distinct things are pinned here, and they are easy to confuse:

  * The bands SHOULD collapse to a single point at the first bar of a session.
    Variance is zero before any volume has accumulated, so vwap == upper ==
    lower there by construction. That convergence is correct and expected.

  * WHERE that collapse lands is what was wrong. The reset was anchored to the
    calendar date, so an overnight 18:00-17:00 session -- one continuous
    session that crosses midnight -- was split at 00:00, six hours in. The
    bands collapsed from 24.56 points wide to zero in the middle of a live
    session and rebuilt from scratch. Measured on ES 2026-08-10..11.
"""

from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analysis.indicators import calc_vwap_bands

NUM_DEV = 2.0


def _bars(start: datetime, count: int, minutes: int = 5, seed: int = 11) -> pd.DataFrame:
    """Synthetic OHLCV on a regular grid, with volume that varies per bar."""
    rng = np.random.default_rng(seed)
    idx = pd.DatetimeIndex([start + timedelta(minutes=minutes * i) for i in range(count)])
    close = 7780 + np.cumsum(rng.normal(0, 1.2, count))
    return pd.DataFrame(
        {
            "high": close + rng.uniform(0.25, 2.0, count),
            "low": close - rng.uniform(0.25, 2.0, count),
            "close": close,
            "volume": rng.integers(50, 500, count).astype(float),
        },
        index=idx,
    )


def _overnight_session() -> pd.DataFrame:
    """18:00 -> 17:00 next day, with the 17:00-18:00 CME break removed."""
    df = _bars(datetime(2026, 8, 10, 0, 0), 24 * 12 * 2)   # two days of 5m bars
    return df[df.index.hour != 17]


def _converged(df, session_start):
    v, u, l = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                              num_dev=NUM_DEV, session_start=session_start)
    mask = (np.isclose(u.values, v.values, atol=1e-9)
            & np.isclose(l.values, v.values, atol=1e-9)
            & v.notna().values)
    return v, u, l, list(df.index[mask])


class TestConvergenceIsExpected:
    """The collapse itself is correct behaviour, not a defect."""

    def test_bands_coincide_at_the_first_bar_of_a_session(self):
        df = _bars(datetime(2026, 8, 10, 9, 30), 78)
        v, u, l, conv = _converged(df, time(9, 30))
        assert df.index[0] in conv, "sigma must be 0 at the first bar of a session"
        assert v.iloc[0] == pytest.approx(u.iloc[0]) == pytest.approx(l.iloc[0])

    def test_bands_fan_out_after_the_first_bar(self):
        df = _bars(datetime(2026, 8, 10, 9, 30), 78)
        v, u, l, _ = _converged(df, time(9, 30))
        width = (u - l).dropna()
        assert width.iloc[0] == pytest.approx(0.0, abs=1e-9)
        assert width.iloc[3] > 0, "bands must widen once variance accumulates"

    def test_bands_are_exactly_num_dev_sigma_from_vwap(self):
        df = _bars(datetime(2026, 8, 10, 9, 30), 78)
        for nd in (1.0, 2.0, 3.0):
            v, u, l = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                                      num_dev=nd, session_start=time(9, 30))
            # upper and lower must stay symmetric about vwap at every bar.
            assert np.allclose((u - v).dropna(), (v - l).dropna())
            # and scale linearly with num_dev.
            base = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                                   num_dev=1.0, session_start=time(9, 30))
            assert np.allclose((u - v).dropna(), nd * (base[1] - base[0]).dropna())


class TestSessionAnchor:
    """WHERE the reset lands -- the actual bug."""

    def test_overnight_session_resets_at_the_session_open_not_midnight(self):
        df = _overnight_session()
        _, _, _, conv = _converged(df, time(18, 0))
        assert any(t.hour == 18 and t.minute == 0 for t in conv), (
            f"expected a reset at an 18:00 bar, got {conv}"
        )
        # The first bar of the supplied data is always a reset (nothing
        # precedes it); every OTHER convergence must be a real session open.
        for t in conv[1:]:
            assert (t.hour, t.minute) == (18, 0), f"unexpected mid-session reset at {t}"

    def test_overnight_session_does_not_collapse_at_midnight(self):
        df = _overnight_session()
        v, u, l, _ = _converged(df, time(18, 0))
        width = (u - l)
        midnights = [t for t in df.index if (t.hour, t.minute) == (0, 0)][1:]
        assert midnights, "fixture must span at least one midnight"
        for t in midnights:
            prev = df.index[df.index.get_loc(t) - 1]
            assert width.loc[t] > 0, f"bands collapsed mid-session at {t}"
            # And no discontinuity: width should carry on from the prior bar.
            assert abs(width.loc[t] - width.loc[prev]) < 1.0, (
                f"band width jumped {width.loc[prev]:.2f} -> {width.loc[t]:.2f} at {t}"
            )

    def test_calendar_anchor_reproduces_the_bug(self):
        # Documents the old behaviour so the test above cannot silently become
        # vacuous if the fixture changes.
        df = _overnight_session()
        v, u, l, conv = _converged(df, None)
        midnights = [t for t in df.index if (t.hour, t.minute) == (0, 0)][1:]
        assert any(t in conv for t in midnights), (
            "with a calendar anchor the bands should still collapse at midnight"
        )

    def test_non_wrapping_session_is_unaffected_by_the_parameter(self):
        # An 09:30-16:00 session sits inside one date, so anchoring on the
        # session open must be identical to anchoring on the calendar date.
        df = _bars(datetime(2026, 8, 10, 9, 30), 78)
        df = pd.concat([df, _bars(datetime(2026, 8, 11, 9, 30), 78, seed=12)])
        a = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                            session_start=None)
        b = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                            session_start=time(9, 30))
        for x, y in zip(a, b):
            assert x.equals(y)

    def test_midnight_session_start_equals_no_session_start(self):
        df = _overnight_session()
        a = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                            session_start=None)
        b = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                            session_start=time(0, 0))
        for x, y in zip(a, b):
            assert x.equals(y)

    def test_each_session_accumulates_independently(self):
        # A session's VWAP must not carry the previous session's mean forward:
        # computing one session alone gives the same numbers as computing it
        # as part of a longer series.
        df = _overnight_session()
        v_all, _, _ = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                                      session_start=time(18, 0))
        opens = [t for t in df.index if (t.hour, t.minute) == (18, 0)]
        assert opens, "fixture must contain a session open"
        start = opens[0]
        one = df[df.index >= start]
        v_one, _, _ = calc_vwap_bands(one["high"], one["low"], one["close"], one["volume"],
                                      session_start=time(18, 0))
        assert np.allclose(v_all.loc[one.index].values, v_one.values, equal_nan=True)


class TestNoVolume:
    def test_all_nan_without_volume(self):
        df = _bars(datetime(2026, 8, 10, 9, 30), 20)
        v, u, l = calc_vwap_bands(df["high"], df["low"], df["close"], None,
                                  session_start=time(9, 30))
        assert v.isna().all() and u.isna().all() and l.isna().all()

    def test_all_nan_when_volume_sums_to_zero(self):
        df = _bars(datetime(2026, 8, 10, 9, 30), 20)
        df["volume"] = 0.0
        v, _, _ = calc_vwap_bands(df["high"], df["low"], df["close"], df["volume"],
                                  session_start=time(9, 30))
        assert v.isna().all()
