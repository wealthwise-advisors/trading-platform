"""Sir's swing-count rules (email 2026-11-12), case by case from his diagrams."""
import numpy as np
import pandas as pd
import pytest

from src.analysis.swing_count import _Pt, calc_swing_count, count_swings, roman, swing_name

STEP = 4  # bars between turning points


def path(points):
    """Candidates at every STEP bars and closes walking straight between them."""
    cands = [_Pt(i * STEP, k, float(p)) for i, (p, k) in enumerate(points)]
    prices = [p for p, _ in points]
    close = np.interp(np.arange((len(points) - 1) * STEP + 1), [c.pos for c in cands], prices)
    return cands, close


def labels(points, **kw):
    cands, close = path(points)
    return [d["label"] for d in count_swings(cands, close, **kw)]


class TestBullishSequence:
    def test_diagram_valid_continuation(self):
        # 0 low, then higher highs closed above the last, higher lows above the last.
        pts = [(100, "L"), (110, "H"), (105, "L"), (115, "H"), (108, "L"), (120, "H"), (112, "L")]
        assert labels(pts) == ["0", "1", "2", "3", "4", "5", "6"]

    def test_odd_points_are_highs_even_points_lows(self):
        pts = [(100, "L"), (110, "H"), (105, "L"), (115, "H"), (108, "L")]
        cands, close = path(pts)
        out = count_swings(cands, close)
        for d in out[1:]:
            assert (int(d["label"]) % 2 == 1) == (d["kind"] == "H")

    def test_a_lower_high_is_not_point_3(self):
        # After 1 (110) and 2 (105), a high of 108 does not take out 1.
        pts = [(100, "L"), (110, "H"), (105, "L"), (108, "H"), (106, "L"), (115, "H")]
        assert labels(pts) == ["0", "1", "2", "3"]
        cands, close = path(pts)
        out = count_swings(cands, close)
        assert out[-1]["price"] == 115

    def test_point_3_needs_a_close_above_point_1(self):
        # The high wicks to 111 above 1 (110), but no candle closes above 110.
        pts = [(100, "L"), (110, "H"), (105, "L"), (111, "H"), (104.5, "L")]
        cands, close = path(pts)
        close = np.minimum(close, 109.5)
        close[STEP] = 110  # point 1's own close
        out = count_swings(cands, close)
        # No 3 yet, so the pullback is still forming: 2 moves down to 104.5,
        # which is still above 0, so the count stays up.
        assert [d["label"] for d in out] == ["0", "1", "2"]
        assert out[-1]["price"] == 104.5

    def test_even_a_small_first_push_is_point_1_and_a_break_of_0_flips(self):
        # Sir's trap rule: 0 -> 1 then a low under 0 makes the move a finished trap.
        pts = [(100, "L"), (101, "H"), (95, "L"), (99, "H"), (90, "L")]
        assert labels(pts) == ["0", "1", "1", "2", "3"]


class TestFlipToLetters:
    def test_diagram_break_of_0_flips_to_a_b_c(self):
        # 0=100, 1=110, the pullback takes out 0 -> A, bounce under old 1 -> B, C below A.
        pts = [(100, "L"), (110, "H"), (95, "L"), (105, "H"), (90, "L")]
        assert labels(pts) == ["0", "1", "1", "2", "3"]

    def test_breaking_point_2_flips_like_breaking_0(self):
        pts = [(100, "L"), (110, "H"), (105, "L"), (115, "H"), (103, "L"), (110, "H"), (98, "L")]
        assert labels(pts) == ["0", "1", "2", "3", "1", "2", "3"]

    def test_bounce_above_old_top_flips_back_to_numbers(self):
        pts = [(100, "L"), (110, "H"), (95, "L"), (112, "H"), (104, "L")]
        assert labels(pts) == ["0", "1", "1", "1", "2"]

    def test_each_direction_is_its_own_run(self):
        pts = [(100, "L"), (110, "H"), (95, "L"), (105, "H"), (90, "L")]
        out = count_swings(*path(pts))
        assert [d["seq"] for d in out] == [1, 1, 2, 2, 2]


class TestSmallCount:
    def test_roman(self):
        assert [roman(n) for n in (1, 2, 3, 4, 5, 9, 14)] == ["i", "ii", "iii", "iv", "v", "ix", "xiv"]

    def test_small_scale_is_roman_in_both_directions(self):
        up = [(100, "L"), (110, "H"), (105, "L"), (115, "H")]
        assert labels(up, scale="small") == ["0", "i", "ii", "iii"]
        flip = [(100, "L"), (110, "H"), (95, "L"), (105, "H"), (90, "L")]
        assert labels(flip, scale="small") == ["0", "i", "i", "ii", "iii"]


def _es_like(seed=3, n=1500):
    rng = np.random.default_rng(seed)
    c = 6000 + np.cumsum(rng.normal(0, 1.2, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 1.5, n)
    lo = np.minimum(o, c) - rng.uniform(0, 1.5, n)
    idx = pd.date_range("2026-11-09 09:30", periods=n, freq="1min")
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=idx)


class TestOnBars:
    @pytest.mark.parametrize("seed", [3, 11, 29])
    def test_every_point_sits_on_its_candle(self, seed):
        df = _es_like(seed)
        zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"])
        assert len(zz10) > 3
        for zz in (zz10, zz3):
            for t, r in zz.iterrows():
                col = "high" if r["type"] == "H" else "low"
                assert df.loc[t, col] == r["price"]

    @pytest.mark.parametrize("seed", [3, 11, 29])
    def test_big_points_alternate_high_and_low(self, seed):
        df = _es_like(seed)
        zz10, _ = calc_swing_count(df["high"], df["low"], df["close"])
        kinds = zz10["type"].tolist()
        assert all(a != b for a, b in zip(kinds, kinds[1:]))

    @pytest.mark.parametrize("seed", [3, 11, 29])
    def test_small_points_fall_inside_their_big_swing(self, seed):
        df = _es_like(seed)
        zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"])
        assert not zz3.empty
        assert set(zz3.index).isdisjoint(set(zz10.index))
        assert zz3.index.min() > zz10.index.min()


class TestOpeningStretch:
    def test_a_low_in_the_first_candles_becomes_point_0(self):
        # A sharp low on candle 3, then a long climb with a turn only later on.
        n = 120
        c = np.r_[np.linspace(105, 95, 4), np.linspace(95, 140, 80), np.linspace(140, 125, 20), np.linspace(125, 150, 16)]
        idx = pd.date_range("2026-11-11 09:30", periods=n, freq="5min")
        df = pd.DataFrame({"high": c + 0.5, "low": c - 0.5, "close": c}, index=idx)
        zz10, _ = calc_swing_count(df["high"], df["low"], df["close"])
        first = zz10.iloc[0]
        assert first["label"] == "0" and first["type"] == "L"
        assert first["price"] == df["low"].min()


def test_an_equal_low_is_a_break_point_2_must_stay_strictly_above():
    pts = [(100, "L"), (110, "H"), (100, "L"), (105, "H"), (95, "L")]
    assert labels(pts) == ["0", "1", "1", "2", "3"]


def test_swings_are_named_by_capital_letters():
    assert [swing_name(n) for n in (1, 2, 3, 26, 27)] == ["A", "B", "C", "Z", "AA"]
