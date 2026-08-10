"""Regular-vs-Expanded Flat measurement, and the OQ-09/OQ-10 abstention.

OQ-09 and OQ-10 were investigated on 356 real flats and left OPEN: neither
"near", "slightly beyond" nor "substantially beyond" has a natural width in
the data. So the quantities are recorded and no flat is ever retyped.

The one exception is FLE-01, which needs no threshold at all -- "wave B
terminates beyond the STARTING level of wave A" is binary geometry. It is
recorded as a fact. It still does not gate: 29 of the 34 structures satisfying
it also satisfy FLU-01, and the reference states no precedence.
"""

import pytest

from src.analysis.elliott_wave import measurements, pipeline
from src.analysis.elliott_wave.models import (
    Direction, EngineConfig, LifecycleState, StructureType, Wave,
)

from .conftest import H, L, pv

M = measurements


def flat(p0=200.0, p1=150.0, p2=180.0, p3=140.0,
         stype=StructureType.FLAT, scale=2, step=10):
    """A 3-leg A-B-C flat from four prices. Defaults describe a down flat:
    A falls 200->150, B retraces to 180, C falls to 140."""
    kinds = [H, L, H, L] if p1 < p0 else [L, H, L, H]
    pivots = [pv(i * step, p, kinds[i], scale)
              for i, p in enumerate((p0, p1, p2, p3))]
    legs = [Wave(id=f"leg{i}", scale=scale, start_pivot=pivots[i],
                 end_pivot=pivots[i + 1], state=LifecycleState.GATED,
                 label="ABC"[i], parent_id="parent") for i in range(3)]
    parent = Wave(id="parent", scale=scale, start_pivot=pivots[0],
                  end_pivot=pivots[3], state=LifecycleState.GATED,
                  structure_type=stype,
                  direction=Direction.DOWN if p1 < p0 else Direction.UP,
                  child_ids=[w.id for w in legs])
    by_id = {w.id: w for w in legs}
    by_id["parent"] = parent
    return parent, by_id


# ── OQ-09: wave B's retracement of wave A ───────────────────────────────────
class TestWaveBRetracement:
    def test_half_retracement(self):
        # A: 200 -> 150 (len 50). B ends at 175 => retraced 25 of 50.
        p, by_id = flat(200.0, 150.0, 175.0, 140.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-01_waveB_retracement_of_waveA"] == pytest.approx(0.5)

    def test_exactly_full_retracement_is_not_beyond(self):
        """B ending exactly AT wave A's start is not 'beyond' it. FLE-01 says
        beyond, and the boundary case must not be counted in."""
        p, by_id = flat(200.0, 150.0, 200.0, 140.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-01_waveB_retracement_of_waveA"] == pytest.approx(1.0)
        assert p.measurements["FLE-01_waveB_beyond_waveA_start"] is False

    def test_beyond_the_start_of_wave_a(self):
        p, by_id = flat(200.0, 150.0, 210.0, 140.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-01_waveB_retracement_of_waveA"] == pytest.approx(1.2)
        assert p.measurements["FLE-01_waveB_beyond_waveA_start"] is True

    def test_works_for_an_up_flat_too(self):
        """A rises 150->200; B falls to 140, past A's start. Same verdict."""
        p, by_id = flat(150.0, 200.0, 140.0, 210.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLE-01_waveB_beyond_waveA_start"] is True

    def test_up_flat_b_short_of_the_start(self):
        p, by_id = flat(150.0, 200.0, 160.0, 210.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLE-01_waveB_beyond_waveA_start"] is False


# ── OQ-10: where wave C lands relative to wave A's end ──────────────────────
class TestWaveCPosition:
    def test_c_beyond_wave_a_end_is_positive(self):
        # A: 200 -> 150. C ends at 130, i.e. 20 past 150, in A's direction.
        p, by_id = flat(200.0, 150.0, 180.0, 130.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-02_FLE-02_waveC_beyond_waveA_end"] == pytest.approx(0.4)

    def test_c_short_of_wave_a_end_is_negative(self):
        """FLU-01's case -- wave C fails to travel the full distance."""
        p, by_id = flat(200.0, 150.0, 180.0, 160.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-02_FLE-02_waveC_beyond_waveA_end"] == pytest.approx(-0.2)

    def test_c_exactly_at_wave_a_end_is_zero(self):
        p, by_id = flat(200.0, 150.0, 180.0, 150.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-02_FLE-02_waveC_beyond_waveA_end"] == 0.0

    def test_sign_is_consistent_for_an_up_flat(self):
        p, by_id = flat(150.0, 200.0, 170.0, 220.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLR-02_FLE-02_waveC_beyond_waveA_end"] == pytest.approx(0.4)

    def test_wave_c_length_is_recorded_relative_to_wave_a(self):
        """Relative to wave A only -- the 'wave AB' base is OQ-11, undefined."""
        p, by_id = flat(200.0, 150.0, 180.0, 130.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["waveC_over_waveA"] == pytest.approx(1.0)


# ── the abstention ──────────────────────────────────────────────────────────
class TestOQ0910Abstention:
    def test_measured_flats_are_tagged_with_both_open_questions(self):
        p, by_id = flat()
        M.record_flat_subtype([p], by_id)
        assert "OQ-09" in p.blocked_by and "OQ-10" in p.blocked_by

    def test_tags_are_not_duplicated(self):
        p, by_id = flat()
        M.record_flat_subtype([p], by_id)
        M.record_flat_subtype([p], by_id)
        assert p.blocked_by.count("OQ-09") == 1
        assert p.blocked_by.count("OQ-10") == 1

    def test_no_flat_subtype_exists_in_the_enum(self):
        present = set(StructureType.__members__)
        assert not (present & {"FLAT_REGULAR", "FLAT_EXPANDED"})

    def test_an_extreme_expanded_shape_is_still_typed_generically(self):
        """B retraces 4x wave A and C runs 6x past its end -- as unambiguously
        'expanded' as anything gets. The engine still declines to say so."""
        p, by_id = flat(200.0, 150.0, 350.0, -150.0)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLE-01_waveB_beyond_waveA_start"] is True
        assert p.measurements["FLR-02_FLE-02_waveC_beyond_waveA_end"] > 5
        assert p.structure_type is StructureType.FLAT
        assert p.state is LifecycleState.GATED

    def test_fle01_does_not_gate_running_flats_out(self):
        """29 of 34 real Running Flats also satisfy FLE-01, and the reference
        states no precedence -- so a running flat keeps its type."""
        p, by_id = flat(200.0, 150.0, 210.0, 160.0,
                        stype=StructureType.FLAT_RUNNING)
        M.record_flat_subtype([p], by_id)
        assert p.measurements["FLE-01_waveB_beyond_waveA_start"] is True
        assert p.structure_type is StructureType.FLAT_RUNNING

    def test_running_flats_are_measured_too(self):
        p, by_id = flat(stype=StructureType.FLAT_RUNNING)
        M.record_flat_subtype([p], by_id)
        assert "FLR-01_waveB_retracement_of_waveA" in p.measurements


class TestScope:
    @pytest.mark.parametrize("stype", [
        StructureType.ZIGZAG, StructureType.IMPULSE,
        StructureType.DOUBLE_THREE])
    def test_non_flat_structures_are_untouched(self, stype):
        p, by_id = flat(stype=stype)
        M.record_flat_subtype([p], by_id)
        assert "FLR-01_waveB_retracement_of_waveA" not in p.measurements
        assert "OQ-09" not in p.blocked_by

    def test_a_zero_length_wave_a_is_skipped_not_divided_by(self):
        p, by_id = flat(200.0, 200.0, 180.0, 140.0)
        M.record_flat_subtype([p], by_id)
        assert "FLR-01_waveB_retracement_of_waveA" not in p.measurements

    def test_a_structure_without_three_legs_is_skipped(self):
        p, by_id = flat()
        p.child_ids = p.child_ids[:2]
        M.record_flat_subtype([p], by_id)
        assert "FLR-01_waveB_retracement_of_waveA" not in p.measurements


# ── end to end ──────────────────────────────────────────────────────────────
class TestThroughPipeline:
    def test_real_analysis_measures_every_flat(self, reference_df):
        res = pipeline.run_analysis(reference_df, EngineConfig())
        flats = [w for w in res.waves if w.structure_type in (
            StructureType.FLAT, StructureType.FLAT_RUNNING)]
        assert flats, "fixture produced no flats to measure"
        for w in flats:
            assert "FLR-01_waveB_retracement_of_waveA" in w.measurements
            assert "OQ-09" in w.blocked_by and "OQ-10" in w.blocked_by

    def test_no_flat_is_ever_retyped_to_a_subtype(self, reference_df):
        res = pipeline.run_analysis(reference_df, EngineConfig())
        for w in res.waves:
            if w.structure_type is not None:
                assert w.structure_type.value not in (
                    "flat_regular", "flat_expanded")

    def test_determinism(self, reference_df):
        def snap():
            r = pipeline.run_analysis(reference_df, EngineConfig())
            return [(w.id,
                     w.measurements.get("FLR-01_waveB_retracement_of_waveA"),
                     w.measurements.get("FLE-01_waveB_beyond_waveA_start"))
                    for w in r.waves]
        assert snap() == snap()
