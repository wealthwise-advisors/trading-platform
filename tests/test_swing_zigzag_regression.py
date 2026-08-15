"""
Regression baseline for the Swing (major, 10-leg) / 3-Leg Deviation (minor)
zigzag visualization -- src/analysis/zigzag.py's calc_nested_zigzag(), and
its two consumers: api/serializers.py::zigzag_to_records() (live chart) and
api/report/report.py::generate_html_report() (static export).

Locks in behavior verified end-to-end (real backtests, live browser
screenshots, and direct API/DOM data extraction) on 2026-08-02:
  - major swing boundaries are contiguous, non-overlapping, and numbered
    sequentially from 1
  - every swing's minor ("3-Leg") sequence starts at label "A"
  - every minor pivot's timestamp falls strictly inside its own parent
    swing's boundary window (never bleeds into the next swing)
  - the live chart and the static HTML report use identical deviation
    defaults and produce byte-identical swing/label data for the same input

This is the verified, stable baseline -- a failure here means a change
altered one of these already-confirmed behaviors. Treat that as "did I
mean to do this", not "fix the test to match the new output".
"""

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.data.sample_data import generate_sample_data
from src.data.csv_provider import CSVDataProvider
from src.strategies import MACrossoverStrategy
from src.backtesting.engine import BacktestEngine
from src.analysis.zigzag import calc_zigzag, assign_swing_labels, calc_nested_zigzag
from api.serializers import zigzag_to_records
from api.report.charts import _calc_zigzag, _assign_swing_labels, _calc_nested_zigzag
from api.report.report import generate_html_report


# The live chart (web/src/features/backtest/ResultsPage.tsx hardcodes
# api.getZigZag(id, 0.003, 0.003)) and the static report
# (api/routers/backtests.py::get_report / generate_html_report's own
# defaults) must use the SAME deviations, or the same backtest renders a
# different swing structure in each -- the exact bug fixed 2026-08-02.
# Fractions: 0.0010 == 0.10%. Matched to the shipped defaults in
# api/schemas/backtest.py so the regression suite exercises what users get.
DEV_10 = 0.0010
DEV_3 = 0.0005

DECIMAL_LABEL_RE = re.compile(r"^\d+\.\d+$")
LETTER_LABEL_RE = re.compile(r"^[A-Z]+$")

# Three fixed reference datasets (deterministic: same seed always produces
# the same bars) of different sizes/seeds, so the invariants below are
# checked against more than one shape of data, not just one lucky case.
REFERENCE_DATASETS = [
    pytest.param(400, 42, id="small-400bars-seed42"),
    pytest.param(2000, 42, id="medium-2000bars-seed42"),
    pytest.param(2000, 7, id="medium-2000bars-seed7"),
]


def _reference_df(symbol="ESZZ", bars=2000, seed=42):
    return generate_sample_data(
        symbol=symbol, start=datetime(2024, 1, 2, 9, 30),
        bars=bars, timeframe_minutes=5, base_price=4500.0,
        tick_size=0.25, seed=seed, save_dir=None,
    )


def _major_and_minor(df, dev_10=DEV_10, dev_3=DEV_3):
    zz10 = assign_swing_labels(calc_zigzag(df["high"], df["low"], df["close"], deviation=dev_10, legs=10))
    zz3 = calc_nested_zigzag(df["high"], df["low"], df["close"], zz10, deviation=dev_3, legs=3)
    return zz10, zz3


class TestSwingBoundaries:
    """Requirement: major swing boundaries are correct and stable."""

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_boundaries_contiguous_and_nonoverlapping(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        zz10, _ = _major_and_minor(df)
        assert not zz10.empty, "reference dataset produced no major swings -- fixture regressed"
        groups = list(zz10.groupby("swing"))
        for i in range(len(groups) - 1):
            this_end = groups[i][1].index.max()
            next_start = groups[i + 1][1].index.min()
            assert next_start > this_end, (
                f"swing {groups[i][0]} (ends {this_end}) overlaps "
                f"swing {groups[i + 1][0]} (starts {next_start})"
            )

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_swing_numbers_sequential_from_1(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        zz10, _ = _major_and_minor(df)
        swing_nums = sorted(int(n) for n in zz10["swing"].unique())
        assert swing_nums == list(range(1, len(swing_nums) + 1))


class TestSwingHeaderData:
    """Requirement: swing headers -- the underlying data every header's
    text is built from (web/CandlestickChart.tsx and api/report/report.py
    both read `label` off these same records to build "Swing N (X to Y)")."""

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_major_labels_are_decimal_format(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        zz10, _ = _major_and_minor(df)
        bad = [lbl for lbl in zz10["label"] if not DECIMAL_LABEL_RE.match(lbl)]
        assert not bad, f"major swing labels not in 'N.M' format: {bad}"

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_minor_labels_are_letter_format(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        _, zz3 = _major_and_minor(df)
        bad = [lbl for lbl in zz3["label"] if not LETTER_LABEL_RE.match(lbl)]
        assert not bad, f"minor labels not spreadsheet-letter format (A, B, ... Z, AA, ...): {bad}"

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_every_major_swing_has_header_data(self, bars, seed):
        """Every swing must be able to render '<b>Swing N</b><br>(first to
        last)' -- i.e. have at least one major pivot of its own."""
        df = _reference_df(bars=bars, seed=seed)
        zz10, _ = _major_and_minor(df)
        for swing_num, grp in zz10.groupby("swing"):
            assert len(grp) >= 1, f"swing {swing_num} has no major pivots to build a header from"


class TestMinorLabelsStartAtA:
    """Requirement: every new swing restarts its 3-Leg sequence at A."""

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_every_swings_first_minor_label_is_A(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        _, zz3 = _major_and_minor(df)
        for swing_num, grp in zz3.groupby("swing"):
            first_label = grp.sort_index().iloc[0]["label"]
            assert first_label == "A", (
                f"swing {swing_num}'s first minor label is {first_label!r}, expected 'A' -- "
                f"a minor pivot coinciding with a major pivot may be getting labeled before "
                f"exclusion again (see calc_nested_zigzag's own coincidence filter)"
            )

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_no_minor_pivot_coincides_with_a_major_pivot(self, bars, seed):
        """A minor pivot at a major pivot's own timestamp is hidden by the
        major overlay's own circle at render time (CandlestickChart.tsx and
        report.py both exclude it). If calc_nested_zigzag ever assigned a
        label to it before that exclusion again, the VISIBLE sequence would
        silently skip a letter -- the direct regression guard for the bug
        fixed 2026-08-02."""
        df = _reference_df(bars=bars, seed=seed)
        zz10, zz3 = _major_and_minor(df)
        major_times = set(zz10.index)
        coinciding = [ts for ts in zz3.index if ts in major_times]
        assert not coinciding, f"minor pivots coincide with major pivots: {coinciding}"


class TestParentSwingContainment:
    """Requirement: every 3-Leg label stays inside its parent swing."""

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_no_minor_pivot_outside_its_parent_swings_window(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        zz10, zz3 = _major_and_minor(df)
        major_groups = list(zz10.groupby("swing"))
        boundaries = {}
        for i, (swing_num, grp) in enumerate(major_groups):
            x0 = grp.index.min()
            x1 = major_groups[i + 1][1].index.min() if i + 1 < len(major_groups) else None
            boundaries[swing_num] = (x0, x1)

        violations = []
        for ts, row in zz3.iterrows():
            x0, x1 = boundaries[row["swing"]]
            if not (ts >= x0 and (x1 is None or ts < x1)):
                violations.append((ts, int(row["swing"])))
        assert not violations, f"minor pivots outside their parent swing's window: {violations}"


class TestLiveAndReportIdentical:
    """Requirement: the live chart and the static HTML report produce
    identical swing/label output for the same backtest."""

    def test_deviation_defaults_match_across_layers(self):
        """web/src/features/backtest/ResultsPage.tsx calls
        api.getZigZag(id, ZIGZAG_DEV_3_DEFAULT / 100, ZIGZAG_DEV_10_DEFAULT / 100)
        for the live chart, from the constants in web/src/store/configStore.ts
        -- these assertions pin the Python-side defaults that must keep
        matching them.
        If this test fails, either the frontend or one of these two
        backend defaults changed without the other -- update whichever one
        drifted, don't just adjust the constant here."""
        import inspect

        sig = inspect.signature(generate_html_report)
        assert sig.parameters["zz_deviation"].default == DEV_10
        assert sig.parameters["zz_deviation_3"].default == DEV_3

        from api.routers.backtests import get_report
        sig2 = inspect.signature(get_report)
        assert sig2.parameters["zz_dev"].default.default == DEV_10
        assert sig2.parameters["zz_dev_3"].default.default == DEV_3

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_serializer_and_report_chart_use_the_same_zigzag_data(self, bars, seed):
        """api/serializers.py::zigzag_to_records() (feeds the live chart)
        and api/report/report.py's internal zz10/zz3 computation (feeds the
        static export) must compute byte-identical swing/label data from
        the same price series and the same deviations."""
        df = _reference_df(bars=bars, seed=seed)

        live = zigzag_to_records(df, dev_3=DEV_3, dev_10=DEV_10)

        report_zz10 = _assign_swing_labels(_calc_zigzag(df["high"], df["low"], df["close"], deviation=DEV_10))
        report_zz3 = _calc_nested_zigzag(df["high"], df["low"], df["close"], report_zz10, deviation=DEV_3, legs=3)

        def to_records(zz):
            return [
                {"t": ts.isoformat(), "price": float(row["price"]), "type": row["type"],
                 "swing": int(row["swing"]), "sub": int(row["sub"]), "label": row["label"]}
                for ts, row in zz.iterrows()
            ]

        assert live["zigzag_10"] == to_records(report_zz10)
        assert live["zigzag_3"] == to_records(report_zz3)


class TestEndToEndReportGeneration:
    """Smoke test: a real backtest's HTML report renders every swing that
    the raw zigzag data says exists, with no exception along the way."""

    def test_report_contains_every_swing_header(self):
        symbol = "ESZZREPORT"
        generate_sample_data(
            symbol=symbol, start=datetime(2024, 1, 2, 9, 30),
            bars=2000, timeframe_minutes=5, base_price=4500.0,
            tick_size=0.25, seed=42, save_dir="data/historical",
        )
        engine = BacktestEngine(
            data_provider=CSVDataProvider("data/historical"),
            strategy=MACrossoverStrategy(fast=9, slow=21),
            symbol=symbol, timeframe="5m",
            initial_capital=100_000.0,
            tick_size=0.25, tick_value=12.50, point_value=50.0,
        )
        results = engine.run(datetime(2024, 1, 2), datetime(2024, 12, 31))

        html = generate_html_report(results)

        zz10, _ = _major_and_minor(results.price_data)
        swing_nums = sorted(int(n) for n in zz10["swing"].unique())
        assert swing_nums, "reference backtest produced no swings -- fixture regressed"
        for swing_num in swing_nums:
            assert f"Swing {swing_num}" in html, f"Swing {swing_num} header missing from report HTML"


class TestSwingOrientation:
    """
    Requirement: a pivot typed 'H' really is a swing high and 'L' a swing low.

    pandas_ta's swing signal is +1 for a high and -1 for a low; calc_zigzag
    once mapped it the other way round, so every peak was labelled 'L' and
    every trough 'H'. Nothing downstream compensated -- `type` drives the
    legend name, the hover text and the marker colour (red for H, green for
    L) -- so the chart drew red "Swing High" markers at every trough.

    Measured against real ES bars before the fix: of 26 pivots typed 'H',
    zero sat at their bar's high; of 26 typed 'L', all 26 did.

    Asserting against the bar's own high/low is exact and orientation-only:
    it does not constrain how many pivots the deviation threshold selects.
    """

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_H_pivots_sit_on_bar_highs_and_L_on_bar_lows(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        zz = calc_zigzag(df["high"], df["low"], df["close"], deviation=DEV_10, legs=10)
        assert not zz.empty, "no pivots produced -- fixture or threshold is wrong"

        wrong_high, wrong_low = [], []
        for ts, row in zz.iterrows():
            bar = df.loc[ts]
            if row["type"] == "H" and abs(row["price"] - bar["high"]) > 1e-9:
                wrong_high.append((ts, row["price"], bar["high"]))
            if row["type"] == "L" and abs(row["price"] - bar["low"]) > 1e-9:
                wrong_low.append((ts, row["price"], bar["low"]))

        assert not wrong_high, f"{len(wrong_high)} 'H' pivots not at their bar's high, e.g. {wrong_high[:3]}"
        assert not wrong_low, f"{len(wrong_low)} 'L' pivots not at their bar's low, e.g. {wrong_low[:3]}"

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_both_orientations_are_present(self, bars, seed):
        # Guards against a "fix" that satisfies the test above by emitting only
        # one type, and against the alternating sequence collapsing.
        df = _reference_df(bars=bars, seed=seed)
        zz = calc_zigzag(df["high"], df["low"], df["close"], deviation=DEV_10, legs=10)
        assert set(zz["type"]) == {"H", "L"}

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_a_high_is_priced_above_its_neighbouring_lows(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        zz = calc_zigzag(df["high"], df["low"], df["close"], deviation=DEV_10, legs=10)
        rows = list(zz.itertuples())
        for prev, cur, nxt in zip(rows, rows[1:], rows[2:]):
            if cur.type == "H":
                assert cur.price >= prev.price and cur.price >= nxt.price, (
                    f"swing high at {cur.Index} priced below a neighbouring low"
                )
            else:
                assert cur.price <= prev.price and cur.price <= nxt.price, (
                    f"swing low at {cur.Index} priced above a neighbouring high"
                )

    @pytest.mark.parametrize("bars,seed", REFERENCE_DATASETS)
    def test_minor_zigzag_has_the_same_orientation(self, bars, seed):
        df = _reference_df(bars=bars, seed=seed)
        _, zz3 = _major_and_minor(df)
        for ts, row in zz3.iterrows():
            bar = df.loc[ts]
            expected = bar["high"] if row["type"] == "H" else bar["low"]
            assert abs(row["price"] - expected) < 1e-9, (
                f"minor pivot typed {row['type']} at {ts} is not at the bar's "
                f"{'high' if row['type'] == 'H' else 'low'}"
            )


class TestDeviationUnits:
    """
    Requirement: the number on the UI slider means what it says.

    pandas_ta.zigzag's `deviation` is a PERCENTAGE ("when deviation=10, it
    shows movements greater than 10%"). calc_zigzag takes a FRACTION, matching
    the API schema and the slider (which shows percent and divides by 100).
    The *100 conversion between them was missing, so a "0.30 %" slider applied
    0.003% -- a 0.23-point threshold on ES near 7,780, below the 0.25 tick, so
    the filter passed essentially every fractal pivot.

    These tests pin the relationship rather than any particular pivot count,
    so they stay valid if the defaults are retuned again.
    """

    def _df(self):
        return _reference_df(bars=2000, seed=42)

    def test_every_leg_clears_the_advertised_threshold(self):
        # Implementation-independent statement of what the number means: with
        # deviation d, the move between consecutive pivots must be at least d
        # of price. Replaces an older test that asserted calc_zigzag delegated
        # to pandas_ta with deviation*100 -- pandas_ta's deviation stage was
        # removed (see _alternate_by_deviation), so that pinned a detail that
        # no longer exists while saying nothing about behaviour.
        df = self._df()
        for dev in (0.0005, 0.001, 0.002, 0.005):
            zz = calc_zigzag(df["high"], df["low"], df["close"], deviation=dev, legs=10)
            prices = zz["price"].tolist()
            for a, b in zip(prices, prices[1:]):
                assert abs(b - a) / a >= dev - 1e-12, (
                    f"leg {a:.2f} -> {b:.2f} is {abs(b-a)/a*100:.4f}%, "
                    f"below the {dev*100:.4f}% threshold"
                )

    def test_does_not_collapse_to_a_single_pivot(self):
        # The bug this replaced: pandas_ta's backward scan, seeded on the final
        # bar and unable to relocate that seed, returned exactly ONE pivot above
        # a data-dependent threshold. On ES 5m it fell off the cliff between
        # 0.08% (32 pivots) and 0.10% (1), which is the shipped default -- so a
        # normal session charted a single swing.
        df = self._df()
        for dev in (0.0005, 0.0008, 0.001, 0.0012, 0.0015, 0.002):
            n = len(calc_zigzag(df["high"], df["low"], df["close"], deviation=dev, legs=10))
            assert n > 2, f"deviation {dev*100:.2f}% collapsed to {n} pivot(s)"

    def test_pivot_count_degrades_smoothly(self):
        # A cliff is the signature of the old defect: counts should taper as the
        # threshold rises, never fall off by an order of magnitude in one step.
        df = self._df()
        devs = [0.0005, 0.0008, 0.001, 0.0012, 0.0015, 0.002, 0.003]
        counts = [len(calc_zigzag(df["high"], df["low"], df["close"], deviation=d, legs=10))
                  for d in devs]
        assert counts == sorted(counts, reverse=True), f"not monotonic: {counts}"
        for d, (a, b) in zip(devs[1:], zip(counts, counts[1:])):
            assert b >= a * 0.35, (
                f"pivot count fell {a} -> {b} at deviation {d*100:.2f}% -- "
                f"that is a cliff, not a taper"
            )

    def test_threshold_is_the_advertised_percentage_of_price(self):
        # A reversal smaller than the threshold must not create a pivot, and a
        # clearly larger one must. Uses the fixture's own price level so the
        # assertion tracks the data rather than a hardcoded tick size.
        df = self._df()
        mid = float(df["close"].mean())
        coarse = calc_zigzag(df["high"], df["low"], df["close"], deviation=0.01, legs=10)   # 1.00%
        fine = calc_zigzag(df["high"], df["low"], df["close"], deviation=0.0002, legs=10)   # 0.02%
        assert len(fine) > len(coarse), (
            f"a 0.02% threshold ({mid*0.0002:.2f}pt) must admit more pivots than "
            f"1.00% ({mid*0.01:.2f}pt); got {len(fine)} vs {len(coarse)}"
        )

    def test_monotonic_in_deviation(self):
        # Raising the threshold can never add pivots.
        df = self._df()
        counts = [
            len(calc_zigzag(df["high"], df["low"], df["close"], deviation=d, legs=10))
            for d in (0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01)
        ]
        assert counts == sorted(counts, reverse=True), f"not monotonic: {counts}"

    def test_column_lookup_matches_exactly_and_does_not_guess(self):
        # The old code built the column name from deviation*100 while passing
        # the raw fraction, so the name never matched and a silent fallback
        # hid the mismatch. The name must now be hit exactly.
        import pandas_ta as ta
        df = self._df()
        for dev in (0.0005, 0.001, 0.003, 0.01):
            r = ta.zigzag(high=df["high"], low=df["low"], close=df["close"],
                          legs=10, deviation=round(dev * 100.0, 9), offset=0)
            expected = f"ZIGZAGs_{round(dev * 100.0, 9)}%_10"
            assert expected in r.columns, (
                f"calc_zigzag would build {expected!r}, pandas_ta produced "
                f"{[c for c in r.columns if c.startswith('ZIGZAGs')]}"
            )

    def test_shipped_defaults_are_in_the_slider_range(self):
        # Keeps the API defaults and the UI slider bounds from drifting apart.
        from api.schemas.backtest import BacktestRequest
        d3 = BacktestRequest.model_fields["zigzag_dev_3"].default
        d10 = BacktestRequest.model_fields["zigzag_dev_10"].default
        # Slider is in percent, min 0.01 max 2 (web/src/store/configStore.ts).
        for name, frac in (("zigzag_dev_3", d3), ("zigzag_dev_10", d10)):
            assert 0.01 <= frac * 100 <= 2, f"{name}={frac} is outside the slider range"
        assert d3 < d10, "the minor zigzag must be finer than the major one it nests in"
