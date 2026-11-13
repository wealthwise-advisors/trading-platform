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


class TestBigAndSmallTogether:
    """Reported 2026-11-12 with a screenshot: "3" and "i" side by side as two
    highs, small points beside the real turn. The chart draws big and small
    points as one line, so they are checked as one line."""

    @pytest.mark.parametrize("seed", [3, 11, 29, 41])
    def test_highs_and_lows_alternate_through_both_counts(self, seed):
        df = _es_like(seed)
        zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"])
        pts = sorted([(t, r["type"]) for t, r in zz10.iterrows()] + [(t, r["type"]) for t, r in zz3.iterrows()])
        assert all(a[1] != b[1] for a, b in zip(pts, pts[1:]))

    @pytest.mark.parametrize("seed", [3, 11, 29, 41])
    def test_every_point_is_the_real_turn_between_its_neighbours(self, seed):
        df = _es_like(seed)
        zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"])
        pts = sorted([(t, r["type"], r["price"]) for t, r in zz10.iterrows()]
                     + [(t, r["type"], r["price"]) for t, r in zz3.iterrows()])
        for p, c, n in zip(pts, pts[1:], pts[2:]):
            seg = df[(df.index > p[0]) & (df.index < n[0])]
            if seg.empty:
                continue
            if c[1] == "H":
                assert seg["high"].max() <= c[2]
            else:
                assert seg["low"].min() >= c[2]

    def test_small_points_count_i_ii_iii_in_order_inside_each_big_move(self):
        df = _es_like(3)
        zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"])
        bounds = list(zz10.index) + [df.index[-1] + pd.Timedelta(minutes=1)]
        for a, b in zip(bounds, bounds[1:]):
            inside = zz3[(zz3.index > a) & (zz3.index < b)]
            assert inside["label"].tolist() == [roman(n) for n in range(1, len(inside) + 1)]


# Real /ES 5m, 10 Nov 2026 09:30-13:30 ET -- the session sir checked.
NOV10 = [
    ("09:30", 7523.0, 7536.0, 7514.5, 7534.5), ("09:35", 7534.75, 7537.25, 7523.25, 7534.5), ("09:40", 7535.0, 7540.75, 7521.0, 7537.0),
    ("09:45", 7537.0, 7537.0, 7522.0, 7529.0), ("09:50", 7529.0, 7532.75, 7520.25, 7527.25), ("09:55", 7527.25, 7551.75, 7525.75, 7551.5),
    ("10:00", 7551.25, 7565.5, 7550.25, 7561.25), ("10:05", 7561.0, 7566.25, 7556.25, 7562.25), ("10:10", 7562.0, 7564.25, 7553.75, 7556.5),
    ("10:15", 7556.25, 7556.75, 7545.75, 7549.5), ("10:20", 7549.5, 7552.75, 7537.0, 7538.5), ("10:25", 7538.75, 7548.5, 7534.5, 7539.75),
    ("10:30", 7540.0, 7549.75, 7538.0, 7546.5), ("10:35", 7546.75, 7547.0, 7533.5, 7535.0), ("10:40", 7535.0, 7535.75, 7522.5, 7522.75),
    ("10:45", 7522.75, 7526.75, 7516.0, 7517.5), ("10:50", 7517.25, 7518.0, 7503.75, 7513.75), ("10:55", 7513.75, 7521.25, 7505.5, 7513.0),
    ("11:00", 7512.75, 7527.0, 7512.0, 7524.5), ("11:05", 7524.5, 7530.0, 7516.5, 7526.5), ("11:10", 7526.5, 7526.75, 7518.75, 7520.0),
    ("11:15", 7520.0, 7529.25, 7515.0, 7520.5), ("11:20", 7520.25, 7523.75, 7512.75, 7523.5), ("11:25", 7523.5, 7525.5, 7512.5, 7522.5),
    ("11:30", 7522.25, 7529.5, 7517.5, 7522.75), ("11:35", 7522.75, 7523.75, 7512.25, 7513.75), ("11:40", 7513.75, 7519.75, 7510.25, 7518.5),
    ("11:45", 7518.25, 7519.0, 7505.0, 7509.5), ("11:50", 7509.25, 7516.75, 7507.5, 7510.75), ("11:55", 7510.5, 7510.5, 7503.0, 7505.75),
    ("12:00", 7505.75, 7514.0, 7503.25, 7511.0), ("12:05", 7511.0, 7515.75, 7507.0, 7515.25), ("12:10", 7515.5, 7522.0, 7515.0, 7518.0),
    ("12:15", 7518.0, 7522.25, 7513.5, 7520.75), ("12:20", 7520.75, 7522.0, 7509.25, 7509.25), ("12:25", 7509.5, 7514.75, 7507.5, 7513.0),
    ("12:30", 7513.0, 7518.5, 7511.75, 7513.0), ("12:35", 7513.0, 7513.25, 7496.25, 7497.5), ("12:40", 7497.75, 7506.0, 7493.0, 7501.75),
    ("12:45", 7501.5, 7504.0, 7495.0, 7502.75), ("12:50", 7503.0, 7509.5, 7499.5, 7507.0), ("12:55", 7506.75, 7513.75, 7505.75, 7510.75),
    ("13:00", 7510.5, 7510.75, 7501.75, 7506.5), ("13:05", 7506.5, 7512.0, 7503.0, 7506.75), ("13:10", 7506.75, 7509.75, 7503.0, 7504.75),
    ("13:15", 7504.75, 7509.75, 7501.75, 7502.75), ("13:20", 7502.75, 7505.75, 7500.5, 7504.0), ("13:25", 7504.0, 7509.5, 7501.5, 7509.25),
    ("13:30", 7509.25, 7519.5, 7508.5, 7515.5),
]

NOV10_PM = [
    ("13:35", 7515.25, 7521.25, 7512.5, 7513.0), ("13:40", 7513.0, 7519.0, 7512.5, 7517.75), ("13:45", 7517.75, 7519.0, 7513.5, 7516.75),
    ("13:50", 7516.75, 7524.0, 7514.5, 7523.25), ("13:55", 7523.25, 7527.0, 7521.5, 7523.0), ("14:00", 7522.75, 7526.0, 7520.75, 7525.75),
    ("14:05", 7525.5, 7534.0, 7522.0, 7533.5), ("14:10", 7533.5, 7535.25, 7523.0, 7524.25), ("14:15", 7524.25, 7528.0, 7521.0, 7527.5),
    ("14:20", 7527.5, 7529.75, 7526.25, 7528.25), ("14:25", 7528.25, 7531.5, 7527.5, 7530.0), ("14:30", 7530.25, 7534.5, 7528.0, 7534.0),
    ("14:35", 7534.0, 7535.0, 7526.25, 7526.5), ("14:40", 7526.5, 7532.25, 7526.5, 7530.5), ("14:45", 7530.5, 7541.0, 7529.75, 7539.5),
    ("14:50", 7539.5, 7542.75, 7534.0, 7534.25), ("14:55", 7534.0, 7536.75, 7531.5, 7533.75), ("15:00", 7533.5, 7534.0, 7524.75, 7526.0),
    ("15:05", 7525.75, 7530.25, 7524.0, 7528.75), ("15:10", 7528.5, 7534.25, 7528.0, 7534.0), ("15:15", 7534.0, 7535.75, 7531.5, 7535.75),
    ("15:20", 7535.75, 7541.5, 7535.0, 7538.5), ("15:25", 7538.25, 7540.5, 7537.0, 7538.75), ("15:30", 7538.5, 7538.75, 7535.0, 7538.25),
    ("15:35", 7538.25, 7540.25, 7536.25, 7538.0), ("15:40", 7538.0, 7539.75, 7536.75, 7537.25), ("15:45", 7537.5, 7547.75, 7536.75, 7547.25),
    ("15:50", 7547.5, 7559.0, 7544.75, 7549.25), ("15:55", 7549.25, 7552.5, 7542.0, 7544.5), ("16:00", 7544.75, 7551.5, 7542.25, 7547.5),
]


def _nov10(rows):
    idx = pd.to_datetime([f"2026-11-10 {r[0]}" for r in rows])
    df = pd.DataFrame([r[1:] for r in rows], index=idx, columns=["open", "high", "low", "close"])
    return calc_swing_count(df["high"], df["low"], df["close"])


class TestNewestPointIsNotLate:
    """The turn finder cannot see the last few candles of a chart, so the
    newest point waited ~6 candles to appear. Real /ES 5m 10 Nov: 15:45 closed
    above C's point 1 (7542.75), 15:50 made 7559, 15:55 closed back below
    15:50's close -- sir's rules make 7559 point 3 there and then."""

    def test_point_3_at_7559_shows_on_the_last_candles(self):
        zz10, _ = _nov10(NOV10 + NOV10_PM)
        c = zz10[zz10["swing"] == 3]
        three = c[c["label"] == "3"]
        assert list(three.index.strftime("%H:%M")) == ["15:50"]
        assert three["price"].iloc[0] == 7559.0

    def test_the_pullback_after_it_is_shown_as_the_forming_point_4(self):
        zz10, _ = _nov10(NOV10 + NOV10_PM)
        last = zz10.iloc[-1]
        assert (last["label"], last["type"], last["price"]) == ("4", "L", 7542.0)


class TestSirNov10:
    """Sir, on the 10 Nov picture: "Swing B starts lower than the last iii".

    The 10:50 low (7503.75) broke point 0, and the bounce to 7530 at 11:05 was
    26 pts with closes above the low -- B's points 1 and 2. A 10:40 candle
    (7535.75) from the fall BEFORE that low hid the bounce from the turn
    finder, so the app merged 7503.75 with 11:55's 7503.00 (a wick 0.75 lower
    that never closed below) and started B there.
    """

    def _count(self):
        idx = pd.to_datetime([f"2026-11-10 {r[0]}" for r in NOV10])
        df = pd.DataFrame([r[1:] for r in NOV10], index=idx, columns=["open", "high", "low", "close"])
        return calc_swing_count(df["high"], df["low"], df["close"])

    def test_swing_b_starts_at_the_low_that_broke_point_0(self):
        zz10, _ = self._count()
        b = zz10[zz10["swing"] == 2]
        one = b[b["label"] == "1"]
        assert list(one.index.strftime("%H:%M")) == ["10:50"]
        assert one["price"].iloc[0] == 7503.75

    def test_the_bounce_to_7530_is_point_2(self):
        zz10, _ = self._count()
        b = zz10[zz10["swing"] == 2]
        two = b[b["label"] == "2"]
        assert list(two.index.strftime("%H:%M")) == ["11:05"]
        assert two["price"].iloc[0] == 7530.0

    def test_a_wick_below_1_without_a_close_is_not_a_point(self):
        zz10, _ = self._count()
        assert "11:55" not in set(zz10.index.strftime("%H:%M"))
        three = zz10[(zz10["swing"] == 2) & (zz10["label"] == "3")]
        assert list(three.index.strftime("%H:%M")) == ["12:40"]


def test_point_3_sits_on_the_top_even_when_the_close_above_1_comes_later():
    # 0=100, 1=110, 2=105. The move wicks to 112 (no close over 110), dips to
    # 107, then a candle at 111.5 closes over 110. Point 3 is the move's top,
    # 112, confirmed by that later close -- not the lower 111.5 (real /ES 3m
    # 2026-11-09: 15:15 wick 7600.50, 15:24 close over point 7 at a 7600.00 high).
    pts = [(100, "L"), (110, "H"), (105, "L"), (112, "H"), (111, "H"), (104, "L")]
    cands, close = path(pts)
    close = np.minimum(close, 109.5)
    close[STEP] = 110          # point 1's own close
    close[4 * STEP] = 110.5    # a later candle of the SAME push closes over 110
    out = count_swings(cands, close)
    three = [d for d in out if d["label"] == "3"]
    assert [d["price"] for d in three] == [112]


def test_a_push_that_turns_back_before_closing_beyond_is_not_the_point():
    # 112 wicks over 1 (110) with no close above, then a real turn back to 107;
    # only the NEXT push (111.5) closes over 110. "Takes out AND closes beyond"
    # is one move: point 3 is 111.5, not 112 (real /ES 3m 2026-11-10 10:48).
    pts = [(100, "L"), (110, "H"), (105, "L"), (112, "H"), (107, "L"), (111.5, "H"), (104, "L")]
    cands, close = path(pts)
    close = np.minimum(close, 109.5)
    close[STEP] = 110
    close[5 * STEP] = 110.5
    out = count_swings(cands, close)
    assert [d["price"] for d in out if d["label"] == "3"] == [111.5]


class TestDownSwingFlipsBackOnlyOnAClose:
    """Sir's email: "If the bounce at 2/B breaks AND CLOSES above the old Point 1
    high, the bearish count fails and flips back to bullish." The up swing ends
    on a close as well (see test_an_up_swing_ends_only_on_a_close_too)."""

    PTS = [(100, "L"), (110, "H"), (95, "L"), (112, "H"), (104, "L")]

    def test_a_wick_above_the_old_high_does_not_flip(self):
        cands, close = path(self.PTS)
        close = np.minimum(close, 109.5)          # the bounce to 112 never closes above 110
        out = count_swings(cands, close)
        assert max(d["seq"] for d in out) == 2, "still the down swing that began after A"

    def test_a_close_above_the_old_high_flips_back(self):
        cands, close = path(self.PTS)             # closes walk straight through 112
        out = count_swings(cands, close)
        assert [d["seq"] for d in out][-2:] == [3, 3]

    def test_an_up_swing_ends_only_on_a_close_too(self):
        # Decided 2026-11-12 (the user's call, after cross-checking common
        # practice): the email let a WICK end an up swing, but every other rule
        # in it -- 1, 3 and the flip back up -- needs a close, and the common
        # standard is "bodies break structure, wicks sweep". Both directions now
        # end on a close; a close AT the level counts (2 must stay STRICTLY above 0).
        cands, close = path([(100, "L"), (110, "H"), (95, "L"), (105, "H"), (90, "L")])
        close = np.maximum(close, 100.5)          # wicks under 0 (100), never closes there
        out = count_swings(cands, close)
        assert max(d["seq"] for d in out) == 1, "a wick under 0 does not end the up swing"

    def test_a_close_under_0_ends_the_up_swing(self):
        cands, close = path([(100, "L"), (110, "H"), (95, "L"), (105, "H"), (90, "L")])
        out = count_swings(cands, close)          # closes walk straight through 95
        assert [(d["seq"], d["price"]) for d in out][:3] == [(1, 100), (1, 110), (2, 95)]



class TestCandleCloseTrigger:
    """Sir's tagging rules (2026-11-13): a high is confirmed when a RED candle
    closes below the close of the last GREEN candle, and tagged on the highest
    wick of the move; a low when a GREEN candle closes above the close of the
    last RED candle, tagged on the lowest wick. Mirrored in a down swing."""

    @staticmethod
    def turns(rows, dev=0.0):
        from src.analysis.swing_count import _trigger_turns
        o, h, l, c = (np.array(col, float) for col in zip(*rows))
        return [(p.pos, p.kind, p.price) for p in _trigger_turns(o, h, l, c, dev)]

    def test_a_red_close_under_the_green_close_confirms_the_high(self):
        rows = [(100, 101, 99, 100.5),   # 0 green
                (100.5, 105, 100, 104),  # 1 green, close 104
                (104, 104.5, 102, 103)]  # 2 red, closes 103 < 104 -> high confirmed
        assert self.turns(rows)[-1] == (1, "H", 105)

    def test_the_red_trigger_that_wicked_higher_is_the_high(self):
        rows = [(100, 104, 99, 103.5),   # 0 green
                (103.5, 106, 102, 103)]  # 1 red, wick 106, closes under 103.5
        assert self.turns(rows)[-1] == (1, "H", 106)

    def test_a_red_close_that_holds_the_green_close_confirms_nothing(self):
        rows = [(100, 105, 99, 104),
                (104.5, 105, 104, 104.2)]   # red, but closes above 104
        assert all(k != "H" for _, k, _ in self.turns(rows))

    def test_a_green_close_over_the_red_close_confirms_the_low(self):
        rows = [(100, 105, 99, 104),      # 0 green
                (104, 104, 98, 99),       # 1 red -> high 105 confirmed
                (99, 99.5, 96, 97),       # 2 red, close 97
                (97, 99, 96.5, 98)]       # 3 green, 98 > 97 -> low confirmed
        assert self.turns(rows)[-1] == (2, "L", 96)

    def test_the_low_is_the_lowest_wick_of_the_whole_pullback(self):
        # Sir's 10 Nov catch: the low one candle before the last red still counts.
        rows = [(100, 105, 99, 104),      # 0 green
                (104, 104, 95, 96),       # 1 red, the pullback's lowest wick 95
                (96, 97, 95.5, 95.8),     # 2 red, the last red before the trigger
                (95.8, 98, 95.6, 97)]     # 3 green, closes over 95.8 -> low confirmed
        assert self.turns(rows)[-1] == (1, "L", 95)

    def test_a_doji_is_neither_green_nor_red(self):
        rows = [(100, 105, 99, 104),
                (104, 104.5, 103, 104)]   # doji: no trigger
        assert self.turns(rows) == []

    def test_a_turn_smaller_than_the_leg_size_is_not_counted(self):
        rows = [(100, 101, 99, 100.5), (100.5, 102, 100, 101.8), (101.8, 101.9, 101.5, 101.6),
                (101.6, 101.8, 101.4, 101.7)]   # a 0.5-point dip: under 0.10%? no -- 0.5% here
        assert len(self.turns(rows, dev=0.01)) == 1, "a 0.5% turn is not a 1% turn"

    def test_a_wide_red_candle_takes_the_low_and_the_high_moves_before_it(self):
        # Real /ES 1W 2025-07-28: a red candle from its high down to the move's
        # low. One candle, one point: the low takes it, and the high moves to the
        # best candle before it (its own higher wick never closed there).
        rows = [(100, 106, 99, 105),      # 0 green
                (105, 105.5, 101, 102),   # 1 red -> high 106 confirmed
                (102, 104, 101.5, 103.5), # 2 green, 103.5 > 102 -> low 101 confirmed
                (104, 104, 95, 97),       # 3 red, high 104 FIRST, then down to 95
                (97, 103, 98, 102)]       # 4 green, 102 > 97 -> low confirmed
        assert self.turns(rows)[-2:] == [(2, "H", 104), (3, "L", 95)]

    def test_a_wide_red_candle_right_after_the_low_extends_that_low(self):
        # Real /ES 1D 2025-06-13: the red candle straight after the low opened at
        # its high and fell below everything -- no candle to keep a high on.
        rows = [(100, 106, 99, 105),      # 0 green
                (105, 105.5, 101, 102),   # 1 red -> high 106
                (102, 103, 100, 102.5),   # 2 green -> low 100 (bar 2)
                (102.5, 104, 95, 97),     # 3 red: high 104 then down to 95
                (97, 103, 98, 102)]       # 4 green -> low
        assert self.turns(rows)[-2:] == [(0, "H", 106), (3, "L", 95)]

    def test_the_count_uses_the_candle_open_for_its_colour(self):
        idx = pd.date_range("2026-11-13 09:30", periods=6, freq="5min")
        df = pd.DataFrame({"open": [100, 100.5, 104, 102, 99, 98], "high": [101, 105, 104.5, 102.5, 99.5, 101],
                           "low": [99, 100, 101, 98, 97, 97.5], "close": [100.5, 104, 102, 99, 98, 100.5]}, index=idx)
        zz10, _ = calc_swing_count(df["high"], df["low"], df["close"], dev_10=0.0, open_=df["open"])
        assert ("H", 105) in list(zip(zz10["type"], zz10["price"]))


def test_a_pullback_candle_closing_above_1_counts_for_point_3():
    # Point 2's own candle closes above point 1: its low came first, so the
    # next higher high is point 3 (real /ES 10m 2026-11-10 14:40).
    pts = [(100, "L"), (110, "H"), (105, "L"), (112, "H"), (104, "L")]
    cands, close = path(pts)
    close = np.minimum(close, 109.5)
    close[STEP] = 110            # point 1's own close
    close[2 * STEP] = 111        # point 2's candle closes above 110
    out = count_swings(cands, close)
    assert [d["price"] for d in out if d["label"] == "3"] == [112]


def test_every_point_is_named_hh_hl_lh_ll_against_the_last_of_its_kind():
    from src.analysis.swing_count import market_structure
    types = ["L", "H", "L", "H", "L", "H", "L"]
    prices = [100, 110, 105, 115, 103, 112, 99]
    assert market_structure(types, prices) == ["L", "H", "HL", "HH", "LL", "LH", "LL"]


class TestOneLeg:
    """The finest level (2026-11-13): every candle-close turn between the
    10 Leg / 3 Leg points, labelled a, b, c ... in each stretch."""

    def _run(self):
        # Minute bars with small wiggles: on 5m every turn is already a 3 Leg
        # turn (0.05%+), so the 1 Leg level is empty there by design.
        from src.analysis.swing_count import calc_fine_swings
        df = _es_like(7, 600)
        zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"], open_=df["open"])
        return df, zz10, zz3, calc_fine_swings(df["open"], df["high"], df["low"], df["close"], zz10, zz3)

    def test_it_finds_points_and_each_sits_on_its_candle(self):
        df, _, _, zz1 = self._run()
        assert len(zz1) > 0
        for t, r in zz1.iterrows():
            assert r["price"] == (df.loc[t, "high"] if r["type"] == "H" else df.loc[t, "low"])

    def test_all_three_levels_together_alternate_high_and_low(self):
        _, zz10, zz3, zz1 = self._run()
        pts = sorted([(t, r["type"]) for zz in (zz10, zz3, zz1) for t, r in zz.iterrows()])
        assert all(a[1] != b[1] for a, b in zip(pts, pts[1:]))

    def test_a_minimum_size_drops_the_smaller_turns(self):
        # The side panel's 1-Leg Deviation (2026-11-14): 0 keeps every turn; a
        # minimum keeps only the turns at least that big, never adds any.
        from src.analysis.swing_count import calc_fine_swings
        df, zz10, zz3, every = self._run()
        some = calc_fine_swings(df["open"], df["high"], df["low"], df["close"], zz10, zz3, deviation=0.0003)
        assert 0 < len(some) < len(every)
        none = calc_fine_swings(df["open"], df["high"], df["low"], df["close"], zz10, zz3, deviation=0.05)
        assert len(none) == 0

    def test_letters_run_a_b_c_in_each_stretch(self):
        _, zz10, zz3, zz1 = self._run()
        anchors = sorted(list(zz10.index) + list(zz3.index))
        for a, b in zip(anchors, anchors[1:] + [zz1.index.max() + pd.Timedelta("1min")]):
            inside = zz1[(zz1.index > a) & (zz1.index < b)]["label"].tolist()
            assert inside == [chr(97 + i) for i in range(len(inside))]

    def test_10_and_3_leg_points_carry_their_hh_hl_label(self):
        _, zz10, zz3, _ = self._run()
        assert set(zz10["structure"]) <= {"H", "L", "HH", "HL", "LH", "LL", "EH", "EL"}
        assert len(zz3) and "structure" in zz3.columns


def test_3_leg_points_start_in_the_first_swing():
    # Every 3 Leg trigger turn inside a big move is shown, from Swing A on --
    # they used to start only at Swing B point 4 on some charts (2026-11-13).
    df = _es_like(3, 800)
    zz10, zz3 = calc_swing_count(df["high"], df["low"], df["close"], open_=df["open"])
    first_swing = zz10[zz10["swing"] == zz10["swing"].min()]
    end = first_swing.index.max()
    assert len(zz3[zz3.index <= end]) > 0
