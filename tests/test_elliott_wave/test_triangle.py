"""Triangle candidate measurement, and the OQ-12/OQ-13 abstention.

TRI-01 ("ABCDE") and TRI-03 ("3-3-3-3-3") are exact and mandatory-tier, and
selective in practice -- 8.4% of five-leg windows pass. They still never gate,
because the reference's own definition of the word ("a sideways movement") has
no derivable threshold and 21% of candidates are plainly trending.

So these tests assert both halves: the quantities ARE recorded, and no
structure is ever named.
"""

import pandas as pd
import pytest

from src.analysis.elliott_wave import hierarchy, pipeline, triangle
from src.analysis.elliott_wave.models import EngineConfig, StructureType

from .conftest import H, L, pv


def window(prices=(100.0, 90.0, 98.0, 92.0, 96.0, 94.0), scale=2, step=60):
    """Six pivots = five sides, alternating H/L. Defaults contract inward."""
    kinds = [H, L, H, L, H, L]
    return [pv(i * step, prices[i], kinds[i], scale) for i in range(6)]


def finer_for(span, per_side=3, scale=1):
    """Place `per_side` finer legs inside every side of `span`."""
    out = []
    for a, b in zip(span, span[1:]):
        gap = (b.index - a.index) / (per_side + 1)
        for j in range(per_side + 1):
            idx = int(a.index + gap * j)
            out.append(pv(idx, 100.0 + j, H if j % 2 else L, scale))
    # dedupe on index, keep sorted -- shared boundaries would double up
    seen, uniq = set(), []
    for p in sorted(out, key=lambda x: x.index):
        if p.index not in seen:
            seen.add(p.index)
            uniq.append(p)
    return uniq


def empty_spans():
    s = hierarchy.SpanIndex()
    s.freeze()
    return s


def flat_rsi_series(n=2000, value=50.0):
    return pd.Series([value] * n)


# ── TRI-01 / TRI-03: what makes a candidate ─────────────────────────────────
class TestCandidateFormation:
    def test_a_well_subdivided_five_leg_window_is_a_candidate(self):
        w = window()
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        assert len(got) == 1

    def test_four_sides_is_not_enough(self):
        w = window()[:5]
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        assert got == []

    def test_a_side_with_too_few_finer_legs_disqualifies_the_window(self):
        """TRI-03 -- every side must subdivide, read as diagonal.py reads
        LD-03/ED-03's 3-3-3-3-3."""
        w = window()
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w, per_side=1)}, empty_spans(), flat_rsi_series())
        assert got == []

    def test_a_side_containing_a_five_wave_disqualifies_the_window(self):
        """3-3-3-3-3 means no side is a five-wave."""
        w = window()
        s = hierarchy.SpanIndex()
        s.add(1, "five_wave", w[0].index, w[1].index)
        s.freeze()
        got = triangle.measure_candidates({2: w, 1: finer_for(w)}, s,
                                          flat_rsi_series())
        assert got == []

    def test_scale_1_produces_nothing(self):
        """No finer scale exists to evaluate TRI-03 against (D-14)."""
        w = window(scale=1)
        got = triangle.measure_candidates({1: w}, empty_spans(), flat_rsi_series())
        assert got == []

    def test_subdivision_counts_are_recorded_per_side(self):
        w = window()
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        counts = got[0]["TRI-03_subdivision_counts"]
        assert len(counts) == 5 and all(n >= 2 for n in counts)


# ── TRI-05: sidewaysness, measured never judged ─────────────────────────────
class TestSidewaysness:
    def test_a_round_trip_scores_near_zero(self):
        w = window(prices=(100.0, 90.0, 100.0, 90.0, 100.0, 100.0))
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        assert got[0]["TRI-05_net_over_path"] == pytest.approx(0.0)

    def test_a_staircase_scores_near_one(self):
        """Net displacement equal to path length -- a pure trend, and the
        engine records it as a candidate anyway rather than judging it."""
        w = window(prices=(100.0, 90.0, 80.0, 70.0, 60.0, 50.0))
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        assert got[0]["TRI-05_net_over_path"] == pytest.approx(1.0)

    def test_a_plainly_trending_window_is_still_recorded_not_rejected(self):
        """21% of real candidates trend. Rejecting them would need a
        'sideways' threshold, which does not exist (OQ-12)."""
        w = window(prices=(100.0, 90.0, 80.0, 70.0, 60.0, 50.0))
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        assert len(got) == 1
        assert got[0]["TRI-05_net_over_path"] > 0.9


# ── TRI-07: the two trendlines that would name the variants ─────────────────
class TestVariantSlopes:
    def test_both_slopes_are_recorded(self):
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        assert r["TRI-07_slope_A_C_E"] is not None
        assert r["TRI-07_slope_B_D"] is not None

    def test_a_flat_top_reads_as_a_zero_slope(self):
        """The kind of geometry that WOULD name a variant -- recorded, unnamed."""
        w = window(prices=(100.0, 90.0, 100.0, 94.0, 100.0, 96.0))
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        assert r["TRI-07_slope_A_C_E"] == pytest.approx(0.0)
        assert r["TRI-07_slope_B_D"] > 0

    def test_no_variant_name_is_ever_produced(self):
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        blob = " ".join(str(k) + str(v) for k, v in r.items()).lower()
        for name in ("ascending", "descending", "contracting", "expanding"):
            assert name not in blob


# ── TRI-06: RSI recorded, "supports" never decided ──────────────────────────
class TestRsi:
    def test_rsi_is_recorded_at_all_six_pivots(self):
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        assert len(r["TRI-06_rsi_at_pivots"]) == 6
        assert all(v == 50.0 for v in r["TRI-06_rsi_at_pivots"])

    def test_a_nan_rsi_reads_as_none_not_zero(self):
        w = window()
        rsi = pd.Series([float("nan")] * 2000)
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), rsi)[0]
        assert r["TRI-06_rsi_at_pivots"] == [None] * 6

    def test_an_out_of_range_pivot_reads_as_none(self):
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), pd.Series([50.0] * 10))[0]
        assert None in r["TRI-06_rsi_at_pivots"]

    def test_no_supports_verdict_is_produced(self):
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        assert not any("support" in str(k).lower() for k in r)


# ── the abstention ──────────────────────────────────────────────────────────
class TestOQ1213Abstention:
    def test_every_candidate_is_tagged(self):
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        assert r["blocked_by"] == ["OQ-12", "OQ-13"]

    def test_triangle_is_not_a_structure_type(self):
        assert "TRIANGLE" not in StructureType.__members__
        assert not any(m.value == "triangle" for m in StructureType)

    def test_candidates_are_dicts_not_waves(self):
        """Promoting them to Wave would put an unnameable shape into the list
        the chart renders as confirmed analysis."""
        w = window()
        got = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())
        assert all(isinstance(x, dict) for x in got)

    def test_a_candidate_carries_its_confirmation_bar(self):
        """No-look-ahead: a consumer must not treat a candidate as known
        before the pivot that closes it has confirmed."""
        w = window()
        r = triangle.measure_candidates(
            {2: w, 1: finer_for(w)}, empty_spans(), flat_rsi_series())[0]
        assert r["confirm_index"] >= r["end_index"]


# ── end to end ──────────────────────────────────────────────────────────────
class TestThroughPipeline:
    def test_candidates_land_on_the_result_and_not_in_waves(self, reference_df):
        res = pipeline.run_analysis(reference_df, EngineConfig())
        assert isinstance(res.triangle_candidates, list)
        for w in res.waves:
            if w.structure_type is not None:
                assert w.structure_type.value != "triangle"

    def test_real_candidates_are_measured_and_tagged(self, reference_df):
        res = pipeline.run_analysis(reference_df, EngineConfig())
        for c in res.triangle_candidates:
            assert c["blocked_by"] == ["OQ-12", "OQ-13"]
            assert len(c["TRI-03_subdivision_counts"]) == 5
            assert len(c["TRI-06_rsi_at_pivots"]) == 6
            assert c["TRI-05_net_over_path"] is None or (
                0.0 <= c["TRI-05_net_over_path"] <= 1.0)

    def test_determinism(self, reference_df):
        def snap():
            r = pipeline.run_analysis(reference_df, EngineConfig())
            return [(c["scale"], c["start_index"], c["end_index"],
                     c["TRI-05_net_over_path"]) for c in r.triangle_candidates]
        assert snap() == snap()

    def test_the_limitation_is_declared_at_runtime(self):
        from src.analysis.elliott_wave import validation
        joined = " ".join(validation.V1_LIMITATIONS).lower()
        assert "triangle" in joined and "never classified" in joined
