"""EXT-01 / EXT-02 measurement, and the OQ-24 abstention.

OQ-24 was investigated against real data and deliberately left OPEN: no
formulation of "extended" showed a cliff, and EXT-02's subdivision criterion
is unmeasurable on almost every impulse. So these tests assert two things in
equal measure -- that the quantities ARE recorded, and that no verdict is ever
reached from them.

The measurement is exercised through `measurements.record_extension` directly
so each assertion pins one behaviour rather than the detector's tuning.
"""

import pandas as pd
import pytest

from src.analysis.elliott_wave import measurements, pipeline
from src.analysis.elliott_wave.models import (
    Direction, EngineConfig, LifecycleState, StructureType, Wave,
)

from .conftest import H, L, pv


def motive(lengths=(40.0, 20.0, 80.0, 30.0, 60.0), scale=2, step=10):
    """A 5-leg up-motive structure with exactly the requested leg lengths.

    Returns (parent, by_id). Prices alternate L,H,L,H,L,H so wave 1/3/5 rise
    and wave 2/4 fall, giving legs of |lengths| in order.
    """
    price = 100.0
    prices = [price]
    for i, ln in enumerate(lengths):
        price += ln if i % 2 == 0 else -ln
        prices.append(price)
    kinds = [L, H, L, H, L, H]
    pivots = [pv(i * step, prices[i], kinds[i], scale) for i in range(6)]

    legs = []
    for i in range(5):
        legs.append(Wave(id=f"leg{i}", scale=scale,
                         start_pivot=pivots[i], end_pivot=pivots[i + 1],
                         state=LifecycleState.GATED,
                         label=str(i + 1), direction=Direction.UP,
                         parent_id="parent"))
    parent = Wave(id="parent", scale=scale,
                  start_pivot=pivots[0], end_pivot=pivots[5],
                  state=LifecycleState.GATED,
                  structure_type=StructureType.IMPULSE,
                  direction=Direction.UP,
                  child_ids=[w.id for w in legs])
    by_id = {w.id: w for w in legs}
    by_id[parent.id] = parent
    return parent, by_id


def finer_pivots(spec, scale=1, step=10):
    """Finer-scale pivots placed inside chosen motive legs.

    `spec` maps a motive leg position (0=w1, 2=w3, 4=w5) to how many finer
    LEGS should sit inside it -- so n legs means n+1 pivots.
    """
    out = []
    for pos, n_legs in spec.items():
        lo = pos * step
        for j in range(n_legs + 1):
            idx = lo + int(step * j / (n_legs + 1))
            out.append(pv(idx, 100.0 + j, H if j % 2 else L, scale))
    return sorted(out, key=lambda p: p.index)


# ── EXT-01: which wave is longest, and by how much ──────────────────────────
class TestEXT01Lengths:
    def test_records_all_three_motive_lengths(self):
        parent, by_id = motive(lengths=(40.0, 20.0, 80.0, 30.0, 60.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_motive_wave_lengths"] == {
            "1": 40.0, "3": 80.0, "5": 60.0}

    def test_identifies_the_longest_motive_wave(self):
        parent, by_id = motive(lengths=(40.0, 20.0, 80.0, 30.0, 60.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] == "3"

    def test_ratio_is_longest_over_second_longest(self):
        parent, by_id = motive(lengths=(40.0, 20.0, 80.0, 30.0, 60.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_over_second"] == pytest.approx(80 / 60)

    def test_wave_1_can_be_the_longest(self):
        parent, by_id = motive(lengths=(90.0, 20.0, 40.0, 30.0, 60.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] == "1"

    def test_wave_5_can_be_the_longest(self):
        parent, by_id = motive(lengths=(40.0, 20.0, 60.0, 30.0, 90.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] == "5"

    def test_wave_2_and_wave_4_are_not_candidates(self):
        """EXT-01 says 'either wave 1, 3, or 5' -- the correctives never win."""
        parent, by_id = motive(lengths=(10.0, 500.0, 20.0, 400.0, 30.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] == "5"
        assert set(parent.measurements["EXT-01_motive_wave_lengths"]) == {"1", "3", "5"}


class TestEXT01Ties:
    """Reject-on-tie, consistent with D-02c."""

    def test_a_tie_for_longest_yields_no_winner(self):
        parent, by_id = motive(lengths=(80.0, 20.0, 80.0, 30.0, 60.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] is None

    def test_a_tie_still_records_the_ratio(self):
        """The ratio is well defined even when the winner is not: it is 1.0."""
        parent, by_id = motive(lengths=(80.0, 20.0, 80.0, 30.0, 60.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_over_second"] == pytest.approx(1.0)

    def test_all_three_equal_is_also_a_tie(self):
        parent, by_id = motive(lengths=(50.0, 20.0, 50.0, 30.0, 50.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] is None


# ── EXT-02: subdivisions, where a finer scale exists ────────────────────────
class TestEXT02Subdivisions:
    def test_scale_1_reports_none_not_zero(self):
        """No finer scale exists (D-14). None means 'unmeasurable'; 0 would
        mean 'measured, and it has none' -- a different and false claim."""
        parent, by_id = motive(scale=1)
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-02_subdivision_counts"] is None
        assert parent.measurements["EXT-02_most_subdivided_wave"] is None
        assert parent.measurements["EXT-02_criteria_agree"] is None

    def test_counts_finer_legs_inside_each_motive_wave(self):
        parent, by_id = motive(scale=2)
        fp = finer_pivots({0: 2, 2: 5, 4: 3}, scale=1)
        measurements.record_extension([parent], by_id, {1: fp})
        counts = parent.measurements["EXT-02_subdivision_counts"]
        assert counts["3"] > counts["5"] > counts["1"]

    def test_most_subdivided_wave_is_identified(self):
        parent, by_id = motive(scale=2)
        fp = finer_pivots({0: 2, 2: 5, 4: 3}, scale=1)
        measurements.record_extension([parent], by_id, {1: fp})
        assert parent.measurements["EXT-02_most_subdivided_wave"] == "3"

    def test_criteria_agree_when_longest_is_also_most_subdivided(self):
        parent, by_id = motive(lengths=(40.0, 20.0, 80.0, 30.0, 60.0), scale=2)
        fp = finer_pivots({0: 2, 2: 5, 4: 3}, scale=1)
        measurements.record_extension([parent], by_id, {1: fp})
        assert parent.measurements["EXT-02_criteria_agree"] is True

    def test_criteria_can_disagree_and_that_is_recorded_not_resolved(self):
        """EXT-02 is conjunctive -- 'elongated WITH exaggerated subdivisions'.
        When the two halves name different waves the rule cannot be satisfied
        as written. Real data does this 36% of the time."""
        parent, by_id = motive(lengths=(40.0, 20.0, 80.0, 30.0, 60.0), scale=2)
        fp = finer_pivots({0: 2, 2: 3, 4: 9}, scale=1)     # w5 most subdivided
        measurements.record_extension([parent], by_id, {1: fp})
        assert parent.measurements["EXT-01_longest_motive_wave"] == "3"
        assert parent.measurements["EXT-02_most_subdivided_wave"] == "5"
        assert parent.measurements["EXT-02_criteria_agree"] is False
        # and nothing was rejected because of it
        assert parent.state is LifecycleState.GATED


# ── OQ-24: measured, never decided ──────────────────────────────────────────
class TestOQ24Abstention:
    def test_every_measured_structure_is_tagged_blocked_by_OQ24(self):
        parent, by_id = motive()
        measurements.record_extension([parent], by_id, {})
        assert "OQ-24" in parent.blocked_by

    def test_the_tag_is_not_duplicated_on_a_second_pass(self):
        parent, by_id = motive()
        measurements.record_extension([parent], by_id, {})
        measurements.record_extension([parent], by_id, {})
        assert parent.blocked_by.count("OQ-24") == 1

    def test_no_verdict_field_is_produced(self):
        parent, by_id = motive(lengths=(10.0, 20.0, 900.0, 30.0, 40.0))
        measurements.record_extension([parent], by_id, {})
        keys = " ".join(parent.measurements).lower()
        for banned in ("is_extended", "has_extension", "extended"):
            assert banned not in keys

    def test_an_enormous_ratio_still_changes_nothing(self):
        """90x the next-longest wave is as far into 'obviously extended' as
        real data ever goes. The engine still declines to say so."""
        parent, by_id = motive(lengths=(10.0, 20.0, 900.0, 30.0, 10.0))
        before_type, before_state = parent.structure_type, parent.state
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_over_second"] == pytest.approx(90.0)
        assert parent.structure_type is before_type
        assert parent.state is before_state

    def test_impulse_with_extension_is_not_a_structure_type(self):
        assert "IMPULSE_WITH_EXTENSION" not in StructureType.__members__
        assert not any(m.value == "impulse_with_extension"
                       for m in StructureType)

    def test_measurement_never_reclassifies_a_structure(self):
        parent, by_id = motive(lengths=(10.0, 20.0, 900.0, 30.0, 40.0))
        measurements.record_extension([parent], by_id, {})
        assert parent.structure_type is StructureType.IMPULSE


# ── scope: which structures get measured ────────────────────────────────────
class TestScope:
    def test_corrective_structures_are_not_measured(self):
        """EXT-01 names motive waves 1, 3 and 5. A zigzag has none."""
        parent, by_id = motive()
        parent.structure_type = StructureType.ZIGZAG
        measurements.record_extension([parent], by_id, {})
        assert "EXT-01_longest_motive_wave" not in parent.measurements
        assert "OQ-24" not in parent.blocked_by

    @pytest.mark.parametrize("stype", [
        StructureType.LEADING_DIAGONAL, StructureType.ENDING_DIAGONAL])
    def test_diagonals_are_measured_too(self, stype):
        """GEN-03's other 5-leg motive forms. A measurement asserts nothing the
        reference did not say; only the impulse case maps to EXT-01's wording."""
        parent, by_id = motive()
        parent.structure_type = stype
        measurements.record_extension([parent], by_id, {})
        assert parent.measurements["EXT-01_longest_motive_wave"] == "3"

    def test_a_structure_without_five_legs_is_skipped(self):
        parent, by_id = motive()
        parent.child_ids = parent.child_ids[:3]
        measurements.record_extension([parent], by_id, {})
        assert "EXT-01_longest_motive_wave" not in parent.measurements


# ── end to end ──────────────────────────────────────────────────────────────
class TestThroughPipeline:
    def test_real_analysis_records_extension_on_motive_structures(self, reference_df):
        res = pipeline.run_analysis(reference_df, EngineConfig())
        motives = [w for w in res.waves if w.structure_type in (
            StructureType.IMPULSE, StructureType.LEADING_DIAGONAL,
            StructureType.ENDING_DIAGONAL)]
        measured = [w for w in motives
                    if "EXT-01_longest_over_second" in w.measurements]
        assert measured, "no motive structure carried an extension measurement"
        for w in measured:
            assert "OQ-24" in w.blocked_by
            assert w.measurements["EXT-01_longest_over_second"] >= 1.0

    def test_no_structure_is_ever_typed_as_an_extension(self, reference_df):
        res = pipeline.run_analysis(reference_df, EngineConfig())
        for w in res.waves:
            if w.structure_type is not None:
                assert w.structure_type.value != "impulse_with_extension"

    def test_oq24_stays_in_the_blocked_registry(self):
        from src.analysis.elliott_wave import validation
        entry = [e for e in validation.BLOCKED_RULES if e["oq"] == "OQ-24"]
        assert entry, "OQ-24 must remain registered as blocked"
        assert set(entry[0]["rules"]) == {"EXT-01", "EXT-02"}

    def test_determinism(self, reference_df):
        def snap():
            r = pipeline.run_analysis(reference_df, EngineConfig())
            return [(w.id, w.measurements.get("EXT-01_longest_motive_wave"),
                     w.measurements.get("EXT-01_longest_over_second"))
                    for w in r.waves]
        assert snap() == snap()
