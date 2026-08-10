"""Pivot detector (SRS §4a): the properties everything else depends on."""

import pandas as pd
import pytest

from src.analysis.elliott_wave import pivots as pv_mod
from src.analysis.elliott_wave.models import EngineConfig, PivotKind

from .conftest import bars_from_path


class TestNoLookAhead:
    """FR-1b. The single most important correctness property of the detector."""

    def test_confirm_index_always_after_index(self, zigzag_bars):
        detected = pv_mod.detect_pivots(zigzag_bars)
        assert detected
        assert all(p.confirm_index > p.index for p in detected)

    def test_truncation_reproduces_confirmed_pivots_exactly(self, zigzag_bars):
        """TR-7a. Cutting the data at bar t must reproduce precisely the pivots
        whose confirm_index < t, with identical indices and prices. If the
        detector peeked ahead, the truncated run would differ."""
        full = pv_mod.detect_pivots(zigzag_bars)
        for frac in (0.3, 0.5, 0.75):
            cut = int(len(zigzag_bars) * frac)
            trunc = pv_mod.detect_pivots(zigzag_bars.iloc[:cut])
            expected = {(p.scale, p.index, p.price) for p in full if p.confirm_index < cut}
            got = {(p.scale, p.index, p.price) for p in trunc}
            assert expected <= got, f"look-ahead detected at cut={cut}"

    def test_trailing_unconfirmed_extreme_is_not_emitted(self):
        """FR-1b.3. A run that ends mid-swing must not emit that final extreme:
        it has no confirmation bar yet."""
        df = bars_from_path([100, 130], bars_per_leg=40)   # one straight leg up
        detected = pv_mod.detect_pivots_at_scale(df, 0.002, 1)
        assert all(p.confirm_index < len(df) for p in detected)
        # the closing high is never reported, because nothing reversed off it
        assert not any(p.index == len(df) - 1 for p in detected)

    def test_visible_at_filters_correctly(self, zigzag_bars):
        detected = pv_mod.detect_pivots(zigzag_bars)
        bar = len(zigzag_bars) // 2
        visible = pv_mod.visible_at(detected, bar)
        assert all(p.confirm_index <= bar for p in visible)
        assert len(visible) < len(detected)


class TestAlternation:
    def test_pivots_strictly_alternate_within_a_scale(self, zigzag_bars):
        """FR-1c.2, guaranteed by construction rather than post-filtering."""
        for scale, plist in pv_mod.by_scale(pv_mod.detect_pivots(zigzag_bars)).items():
            kinds = [p.kind for p in plist]
            for a, b in zip(kinds, kinds[1:]):
                assert a != b, f"scale {scale} has two consecutive {a}"

    def test_pivot_price_is_the_bar_extreme(self, zigzag_bars):
        """FR-1c.1: high for a HIGH pivot, low for a LOW pivot -- the same
        convention IMP-04/05/06 rely on."""
        for p in pv_mod.detect_pivots(zigzag_bars):
            bar = zigzag_bars.iloc[p.index]
            expected = bar["high"] if p.kind is PivotKind.HIGH else bar["low"]
            assert p.price == pytest.approx(float(expected))

    def test_indices_are_strictly_increasing_per_scale(self, zigzag_bars):
        for plist in pv_mod.by_scale(pv_mod.detect_pivots(zigzag_bars)).values():
            idx = [p.index for p in plist]
            assert idx == sorted(idx)
            assert len(set(idx)) == len(idx)


class TestDeterminism:
    def test_repeated_runs_identical(self, zigzag_bars):
        sig = lambda: [(p.scale, p.index, p.confirm_index, p.price, p.kind.value)
                       for p in pv_mod.detect_pivots(zigzag_bars)]
        first = sig()
        for _ in range(19):
            assert sig() == first

    def test_input_frame_is_not_mutated(self, zigzag_bars):
        """FR-1a.3."""
        before = zigzag_bars.copy(deep=True)
        pv_mod.detect_pivots(zigzag_bars)
        pd.testing.assert_frame_equal(zigzag_bars, before)


class TestMultiScale:
    def test_coarser_scale_never_has_more_pivots(self, zigzag_bars):
        by = pv_mod.by_scale(pv_mod.detect_pivots(zigzag_bars))
        counts = [len(by.get(k, [])) for k in sorted(by)]
        assert counts == sorted(counts, reverse=True)

    def test_containment_is_measured_not_assumed(self, zigzag_bars):
        """FR-1d.4 / TR-7b. The engine must REPORT the containment rate. It is
        high in practice (99-100%) but the code must not depend on it being 1.0."""
        from src.analysis.elliott_wave import hierarchy
        by = pv_mod.by_scale(pv_mod.detect_pivots(zigzag_bars))
        measured = False
        for k in sorted(by):
            if k - 1 in by:
                rate = hierarchy.containment_rate(by[k], by[k - 1])
                if rate is not None:
                    assert 0.0 <= rate <= 1.0
                    measured = True
        assert measured, "no adjacent scale pair to measure"

    def test_thresholds_follow_the_configured_ladder(self):
        cfg = EngineConfig(theta_base=0.001, ratio=4.0, scales=4)
        assert cfg.thresholds() == pytest.approx([0.001, 0.004, 0.016, 0.064])

    def test_scale_index_is_not_a_degree(self, zigzag_bars):
        """FR-1d.3 / OQ-17 still open: pivots carry an integer ladder index and
        no named Elliott degree."""
        p = pv_mod.detect_pivots(zigzag_bars)[0]
        assert isinstance(p.scale, int)
        assert not hasattr(p, "degree")
        assert not hasattr(p, "degree_name")


class TestEdgeCases:
    def test_empty_frame(self):
        assert pv_mod.detect_pivots(pd.DataFrame()) == []

    def test_single_bar(self):
        df = bars_from_path([100, 100], bars_per_leg=1).iloc[:1]
        assert pv_mod.detect_pivots(df) == []

    def test_monotonic_series_yields_only_the_seeded_origin(self):
        """A pure one-directional rise contains exactly one real turn: the bar
        the move started from. The detector reports that origin low (once price
        has risen past the threshold) and nothing else -- in particular no
        pivot at the unconfirmed final bar."""
        df = bars_from_path([100, 400], bars_per_leg=80)
        detected = pv_mod.detect_pivots(df)
        assert all(p.kind is PivotKind.LOW for p in detected)
        assert all(p.index == 0 for p in detected), "only the origin may pivot"
        assert all(p.confirm_index < len(df) for p in detected)
        # at most one per scale, never a run of them
        assert len(detected) <= 4

    def test_flat_series_produces_nothing(self):
        df = bars_from_path([100, 100, 100], bars_per_leg=30)
        assert pv_mod.detect_pivots(df) == []

    def test_missing_columns_raise_clearly(self):
        df = pd.DataFrame({"close": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required column"):
            pv_mod.detect_pivots(df)

    def test_non_positive_theta_rejected(self, zigzag_bars):
        with pytest.raises(ValueError):
            pv_mod.detect_pivots_at_scale(zigzag_bars, 0.0, 1)

    def test_exhausted_scale_contributes_nothing_without_raising(self):
        """ARCHITECTURE §5.5: a coarse scale with <2 pivots is normal on short
        inputs and must not crash the run."""
        df = bars_from_path([100, 103, 100, 103], bars_per_leg=5)
        cfg = EngineConfig(theta_base=0.001, ratio=10.0, scales=4)
        detected = pv_mod.detect_pivots(df, cfg)
        by = pv_mod.by_scale(detected)
        assert len(by.get(4, [])) < 2      # coarsest is exhausted
