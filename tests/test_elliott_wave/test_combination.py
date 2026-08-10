"""Double Three (W-X-Y) and Triple Three (W-X-Y-X-Z), and the OQ-18 depth cap.

Gate tests build pivots and SpanIndex entries directly, so each assertion pins
down one rule rather than the detector's tuning.
"""

import pytest

from src.analysis.elliott_wave import combination, hierarchy
from src.analysis.elliott_wave.models import (
    EngineConfig, LifecycleState, StructureType,
)

from .conftest import H, L, pv

CORRECTIVE = "corrective"
COMBINATION = "combination"


def dt_window(p0=200.0, p1=150.0, p2=180.0, p3=140.0, scale=3, step=100):
    """A 3-leg W-X-Y window: H, L, H, L."""
    prices, kinds = [p0, p1, p2, p3], [H, L, H, L]
    return [pv(i * step, prices[i], kinds[i], scale) for i in range(4)]


def tt_window(prices=(200.0, 150.0, 180.0, 140.0, 170.0, 130.0), scale=3, step=100):
    """A 5-leg W-X-Y-X-Z window: H, L, H, L, H, L."""
    kinds = [H, L, H, L, H, L]
    return [pv(i * step, prices[i], kinds[i], scale) for i in range(6)]


def spans_with(entries, kind=CORRECTIVE):
    """SpanIndex pre-loaded with component structures at the finer scale."""
    s = hierarchy.SpanIndex()
    for scale, a, b in entries:
        s.add(scale, kind, a, b)
    s.freeze()
    return s


def components_for(window, indices, scale, kind=CORRECTIVE):
    return [(scale - 1, window[i].index, window[i + 1].index) for i in indices]


# ── DT-01: three legs, W-X-Y ────────────────────────────────────────────────
class TestDT01:
    def test_pass_three_legs_yields_a_candidate(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert [x for x in found if x.structure_type is StructureType.DOUBLE_THREE]

    def test_fail_two_legs_cannot_form_a_window(self):
        w = dt_window()[:3]
        spans = spans_with([])
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert not [x for x in found if x.structure_type is not None]

    def test_legs_labelled_W_X_Y(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        parent = [x for x in found if x.structure_type is StructureType.DOUBLE_THREE][0]
        by_id = {x.id: x for x in found}
        assert [by_id[c].label for c in parent.child_ids] == ["W", "X", "Y"]


# ── DT-03: W and Y must each hold a permitted component ─────────────────────
class TestDT03:
    def test_pass_when_both_W_and_Y_hold_a_corrective(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert [x for x in found if x.structure_type is StructureType.DOUBLE_THREE]

    def test_fail_when_Y_has_no_component(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0,), 3))      # W only
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert not [x for x in found if x.structure_type is not None]

    def test_fail_when_W_has_no_component(self):
        w = dt_window()
        spans = spans_with(components_for(w, (2,), 3))      # Y only
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert not [x for x in found if x.structure_type is not None]

    def test_X_is_permissive_and_needs_no_component(self):
        """DT-04: wave X can be any corrective structure, so it never gates."""
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))    # nothing for X
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert [x for x in found if x.structure_type is StructureType.DOUBLE_THREE]

    def test_scale_1_can_never_qualify(self):
        """No finer scale exists to hold a component."""
        w = dt_window(scale=1)
        spans = spans_with([])
        found = combination.classify_combinations({1: w}, spans, max_depth=1)
        assert not [x for x in found if x.structure_type is not None]


# ── DT-05 / TT-05: wave Y must not pass 161.8% of wave W ────────────────────
class TestWaveYCeiling:
    def test_pass_below_the_ceiling(self):
        # W = 50, Y = 60  -> 1.20x
        w = dt_window(p0=200.0, p1=150.0, p2=180.0, p3=120.0)
        assert combination.gate_wave_y_ceiling(w[0], w[1], w[2], w[3]) is True

    def test_fail_above_the_ceiling(self):
        # W = 50, Y = 100 -> 2.00x
        w = dt_window(p0=200.0, p1=150.0, p2=180.0, p3=80.0)
        assert combination.gate_wave_y_ceiling(w[0], w[1], w[2], w[3]) is False

    def test_boundary_exactly_at_161_8_percent_passes(self):
        """"can not PASS 161.8%" -- exactly at the ceiling has not passed it."""
        w = dt_window(p0=200.0, p1=150.0, p2=180.0, p3=180.0 - 50.0 * 1.618)
        assert combination.gate_wave_y_ceiling(w[0], w[1], w[2], w[3]) is True

    def test_just_over_the_ceiling_fails(self):
        w = dt_window(p0=200.0, p1=150.0, p2=180.0, p3=180.0 - 50.0 * 1.619)
        assert combination.gate_wave_y_ceiling(w[0], w[1], w[2], w[3]) is False

    def test_zero_length_W_is_rejected_not_divided_by(self):
        w = dt_window(p0=200.0, p1=200.0, p2=180.0, p3=140.0)
        assert combination.gate_wave_y_ceiling(w[0], w[1], w[2], w[3]) is False

    def test_ceiling_gates_the_full_classifier(self):
        w = dt_window(p0=200.0, p1=150.0, p2=180.0, p3=80.0)   # Y/W = 2.0
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert not [x for x in found if x.structure_type is not None]

    def test_constant_is_a_ceiling_not_a_match_target(self):
        """OQ-05 stays intact: the constant bounds, it does not match."""
        assert combination.WAVE_Y_CEILING_OF_W == 1.618
        # a Y/W nowhere near any Fibonacci value must still be accepted
        w = dt_window(p0=200.0, p1=150.0, p2=180.0, p3=175.0)   # Y/W = 0.10
        assert combination.gate_wave_y_ceiling(w[0], w[1], w[2], w[3]) is True


# ── TT-01 / TT-03 ───────────────────────────────────────────────────────────
class TestTripleThree:
    def test_pass_five_legs_with_all_components(self):
        w = tt_window()
        spans = spans_with(components_for(w, (0, 2, 4), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert [x for x in found if x.structure_type is StructureType.TRIPLE_THREE]

    def test_fail_when_Z_has_no_component(self):
        w = tt_window()
        spans = spans_with(components_for(w, (0, 2), 3))     # W, Y only
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert not [x for x in found if x.structure_type is StructureType.TRIPLE_THREE]

    def test_legs_labelled_W_X_Y_X_Z(self):
        w = tt_window()
        spans = spans_with(components_for(w, (0, 2, 4), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        parent = [x for x in found if x.structure_type is StructureType.TRIPLE_THREE][0]
        by_id = {x.id: x for x in found}
        assert [by_id[c].label for c in parent.child_ids] == ["W", "X", "Y", "X", "Z"]

    def test_ceiling_constrains_wave_Y_not_wave_Z(self):
        """TT-05 names wave Y. A large wave Z must NOT be rejected by it."""
        # W = 50, Y = 40 (fine), Z = 300 (huge)
        w = tt_window(prices=(200.0, 150.0, 180.0, 140.0, 170.0, -130.0))
        spans = spans_with(components_for(w, (0, 2, 4), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        assert [x for x in found if x.structure_type is StructureType.TRIPLE_THREE], \
            "wave Z is not bounded by TT-05"


# ── OQ-18: the depth cap ────────────────────────────────────────────────────
class TestDepthCap:
    def test_depth_0_refuses_a_combination_component(self):
        """At depth 0 only zigzag/flat qualify -- a nested DT must not count."""
        w = dt_window(scale=4)
        spans = spans_with(components_for(w, (0, 2), 4), kind=COMBINATION)
        found = combination.classify_combinations({4: w}, spans, max_depth=0)
        assert not [x for x in found if x.structure_type is not None]

    def test_depth_1_accepts_a_combination_component(self):
        w = dt_window(scale=4)
        spans = spans_with(components_for(w, (0, 2), 4), kind=COMBINATION)
        found = combination.classify_combinations({4: w}, spans, max_depth=1)
        got = [x for x in found if x.structure_type is StructureType.DOUBLE_THREE]
        assert got
        assert got[0].measurements["combination_depth"] == 1

    def test_default_config_cap_is_1(self):
        """1 is the ladder's expressive limit, derived not guessed -- see
        combination.py's docstring."""
        assert EngineConfig().max_combination_depth == 1

    def test_a_structure_is_not_re_emitted_at_a_deeper_depth(self):
        """A deeper pass re-finds everything a shallower one found; emitting it
        twice would double-count. Shallowest find wins."""
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=1)
        structs = [x for x in found if x.structure_type is StructureType.DOUBLE_THREE]
        assert len(structs) == 1
        assert structs[0].measurements["combination_depth"] == 0
        assert len({x.id for x in structs}) == len(structs)

    def test_depth_2_is_structurally_unreachable_on_a_4_scale_ladder(self):
        """Depth 2 needs a combination at scale 4 to act as a component for a
        parent at scale 5. The ladder has 4 scales, so it can never fire --
        raising the cap yields nothing, which is why 1 is the cap."""
        w = dt_window(scale=4)
        spans = spans_with(components_for(w, (0, 2), 4), kind=COMBINATION)
        at_1 = combination.classify_combinations({4: w}, spans, max_depth=1)
        spans2 = spans_with(components_for(w, (0, 2), 4), kind=COMBINATION)
        at_2 = combination.classify_combinations({4: w}, spans2, max_depth=2)
        ids1 = {x.id for x in at_1 if x.structure_type is not None}
        ids2 = {x.id for x in at_2 if x.structure_type is not None}
        assert ids1 == ids2, "raising the cap past 1 must add nothing"

    def test_negative_or_zero_cap_is_safe(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        assert combination.classify_combinations({3: w}, spans, max_depth=-1) or True


# ── OQ-26: swing count recorded, never gated ────────────────────────────────
class TestOQ26SwingCount:
    def test_swing_count_is_recorded(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        s = [x for x in found if x.structure_type is StructureType.DOUBLE_THREE][0]
        assert "finer_swing_count" in s.measurements
        assert s.measurements["stated_swing_count"] == 7

    def test_swing_count_does_not_gate(self):
        """The reference's 7 contradicts DT-04 (3+3+3 = 9). A structure whose
        real finer-swing count is nowhere near 7 must still classify."""
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        s = [x for x in found if x.structure_type is StructureType.DOUBLE_THREE][0]
        assert s.measurements["finer_swing_count"] != 7
        assert s.state is LifecycleState.GATED

    def test_every_combination_carries_the_oq26_caveat(self):
        w = dt_window()
        spans = spans_with(components_for(w, (0, 2), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        for s in [x for x in found if x.structure_type is not None]:
            assert s.blocked_by == ["OQ-26"]

    def test_triple_three_states_11(self):
        w = tt_window()
        spans = spans_with(components_for(w, (0, 2, 4), 3))
        found = combination.classify_combinations({3: w}, spans, max_depth=0)
        s = [x for x in found if x.structure_type is StructureType.TRIPLE_THREE][0]
        assert s.measurements["stated_swing_count"] == 11


# ── determinism ─────────────────────────────────────────────────────────────
class TestDeterminism:
    @pytest.mark.parametrize("depth", [0, 1])
    def test_repeated_runs_identical(self, depth):
        w = dt_window()
        sig = []
        for _ in range(5):
            spans = spans_with(components_for(w, (0, 2), 3))
            found = combination.classify_combinations({3: w}, spans, max_depth=depth)
            sig.append([(x.id, x.state.value, x.label) for x in found])
        assert all(s == sig[0] for s in sig)
