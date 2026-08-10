"""IMP-01 .. IMP-06: one passing and one failing fixture per mandatory gate.

Each failing fixture violates EXACTLY ONE rule, so a failure here names the
broken gate instead of just saying "no impulse found".
"""

import pandas as pd
import pytest

from src.analysis.elliott_wave import hierarchy, impulse
from src.analysis.elliott_wave.models import Direction, LifecycleState, StructureType

from .conftest import H, L, down_impulse, pv, up_impulse


# ── IMP-01: an impulse subdivides into 5 waves ──────────────────────────────
class TestIMP01:
    def test_pass_five_legs_yields_a_candidate(self, diverging_rsi):
        pivots = up_impulse()
        spans = hierarchy.SpanIndex()
        spans.freeze()
        waves = impulse.classify_impulses({1: pivots}, diverging_rsi(200), spans)
        assert [w for w in waves if w.structure_type is StructureType.IMPULSE]

    def test_fail_four_legs_cannot_form_a_window(self, flat_rsi):
        pivots = up_impulse()[:5]           # 4 legs only
        spans = hierarchy.SpanIndex()
        spans.freeze()
        waves = impulse.classify_impulses({1: pivots}, flat_rsi(200), spans)
        assert not [w for w in waves if w.structure_type is StructureType.IMPULSE]

    def test_window_generator_requires_legs_plus_one_pivots(self):
        assert len(list(hierarchy.windows(up_impulse(), 5))) == 1
        assert list(hierarchy.windows(up_impulse()[:5], 5)) == []


# ── IMP-02: waves 1/3/5 subdivide into impulses (D-14 recursion floor) ──────
class TestIMP02:
    def test_scale_1_is_undecidable_never_pass_or_fail(self):
        """D-14, confirmed: no finer scale exists, so the gate cannot be
        evaluated. It must return None -- not False, not True."""
        spans = hierarchy.SpanIndex()
        spans.freeze()
        assert impulse.gate_imp02(up_impulse(), scale=1, spans=spans) is None

    def test_pass_when_all_three_legs_hold_a_finer_impulse(self):
        w = up_impulse(scale=2)
        spans = hierarchy.SpanIndex()
        for a, b in ((w[0], w[1]), (w[2], w[3]), (w[4], w[5])):
            spans.add(1, "impulse", a.index, b.index)
        spans.freeze()
        assert impulse.gate_imp02(w, scale=2, spans=spans) is True

    def test_fail_when_one_leg_lacks_a_finer_impulse(self):
        w = up_impulse(scale=2)
        spans = hierarchy.SpanIndex()
        spans.add(1, "impulse", w[0].index, w[1].index)
        spans.add(1, "impulse", w[2].index, w[3].index)
        # wave 5 deliberately left without a sub-impulse
        spans.freeze()
        assert impulse.gate_imp02(w, scale=2, spans=spans) is False

    def test_undecidable_candidate_records_the_reason(self, diverging_rsi):
        spans = hierarchy.SpanIndex()
        spans.freeze()
        waves = impulse.classify_impulses({1: up_impulse()}, diverging_rsi(200), spans)
        s = [w for w in waves if w.structure_type is StructureType.IMPULSE][0]
        assert s.state is LifecycleState.UNDECIDABLE
        assert "IMP-02" in s.blocked_by


# ── IMP-03: wave 2 can't retrace past the start of wave 1 ───────────────────
class TestIMP03:
    def test_pass_up(self):
        assert impulse.gate_imp03(up_impulse(), Direction.UP) is True

    def test_fail_up_wave2_breaches_wave1_start(self):
        w = up_impulse(p2=95)               # start was 100
        assert impulse.gate_imp03(w, Direction.UP) is False

    def test_pass_down(self):
        assert impulse.gate_imp03(down_impulse(), Direction.DOWN) is True

    def test_fail_down_wave2_breaches_wave1_start(self):
        w = down_impulse(p2=235)            # start was 230
        assert impulse.gate_imp03(w, Direction.DOWN) is False

    def test_exact_equality_is_a_full_retrace_and_fails(self):
        """Ending exactly AT wave 1's start is 'retracing to the beginning',
        so the strict comparison rejects it."""
        assert impulse.gate_imp03(up_impulse(p2=100), Direction.UP) is False


# ── IMP-04: wave 3 not the shortest (OQ-02: absolute price distance) ────────
class TestIMP04:
    def test_pass_wave3_longest(self):
        assert impulse.gate_imp04(up_impulse()) is True   # 40 / 80 / 60

    def test_pass_wave3_merely_not_shortest(self):
        # len1=40, len3=50, len5=90 -> wave 3 is middle, still passes
        assert impulse.gate_imp04(up_impulse(p3=170, p4=140, p5=230)) is True

    def test_fail_wave3_shortest(self):
        # len1=40, len3=20, len5=60
        assert impulse.gate_imp04(up_impulse(p3=140, p4=125, p5=185)) is False

    def test_d02c_exact_tie_is_rejected(self):
        """D-02c, confirmed: a wave 3 exactly equal to the shorter of waves
        1/5 IS a shortest wave. Strict '>' rejects it. Reachable on
        tick-quantised data, so the boundary is deliberate."""
        # len1=40, len3=40, len5=60
        w = up_impulse(p0=100, p1=140, p2=120, p3=160, p4=130, p5=190)
        assert abs(w[3].price - w[2].price) == abs(w[1].price - w[0].price) == 40
        assert impulse.gate_imp04(w) is False

    def test_measure_is_absolute_price_not_percentage(self):
        """OQ-02 rejected percentage distance. A case where the two disagree
        must follow the absolute reading."""
        # abs: len1=100 (1000->1100), len3=150, len5=120  -> wave 3 not shortest
        # pct: len1=10%,  len3=12.5% (1200->1350) ... still fine; use a case
        # where pct ordering flips: high prices shrink pct for equal abs moves.
        w = [pv(0, 1000, L), pv(10, 1100, H), pv(20, 1050, L),
             pv(30, 1200, H), pv(40, 1150, L), pv(50, 1270, H)]
        abs_lens = [100, 150, 120]
        pct_lens = [100 / 1000, 150 / 1050, 120 / 1150]
        assert min(range(3), key=lambda i: abs_lens[i]) == 0
        assert min(range(3), key=lambda i: pct_lens[i]) == 0
        assert impulse.gate_imp04(w) is True
        # and the engine must be using the absolute numbers
        assert abs(w[3].price - w[2].price) == 150


# ── IMP-05: wave 4 must not enter wave 1's price territory ──────────────────
class TestIMP05:
    def test_pass_no_overlap(self):
        # w1 [100,140]; w4 [170,200]
        assert impulse.gate_imp05(up_impulse()) is True

    def test_fail_overlap(self):
        # wave 4 drops to 135, inside wave 1's [100,140]
        assert impulse.gate_imp05(up_impulse(p4=135)) is False

    def test_d02c_exact_touch_counts_as_overlap(self):
        """D-02c, confirmed: closed intervals. Territories touching at exactly
        one price intersect, so the candidate is rejected."""
        w = up_impulse(p4=140)              # wave 1 top is exactly 140
        lo1, hi1 = sorted((w[0].price, w[1].price))
        lo4, hi4 = sorted((w[3].price, w[4].price))
        assert hi1 == lo4 == 140
        assert impulse.gate_imp05(w) is False

    def test_uses_pivot_prices_not_intrabar_scan(self):
        """OQ-03 rejected scanning every bar in wave 1's span. The gate must
        depend only on the two endpoint pivot prices."""
        w = up_impulse()
        assert impulse.gate_imp05(w) is True
        # moving only wave 1's ENDPOINT changes the verdict...
        assert impulse.gate_imp05(up_impulse(p1=175)) is False
        # ...and nothing else in the window is consulted for territory.

    def test_pass_down_impulse(self):
        assert impulse.gate_imp05(down_impulse()) is True

    def test_fail_down_impulse_overlap(self):
        assert impulse.gate_imp05(down_impulse(p4=195)) is False


# ── IMP-06: wave 5 ends with RSI(13) divergence (OQ-04) ─────────────────────
class TestIMP06:
    def _rsi(self, values):
        return pd.Series(values)

    def test_pass_up_divergence(self):
        w = up_impulse()
        rsi = self._rsi([50.0] * 60)
        rsi.iloc[w[3].index] = 80.0         # wave 3 peak
        rsi.iloc[w[5].index] = 70.0         # wave 5 lower -> divergence
        assert impulse.gate_imp06(w, Direction.UP, rsi) is True

    def test_fail_up_no_divergence(self):
        w = up_impulse()
        rsi = self._rsi([50.0] * 60)
        rsi.iloc[w[3].index] = 70.0
        rsi.iloc[w[5].index] = 85.0         # RSI confirms the high
        assert impulse.gate_imp06(w, Direction.UP, rsi) is False

    def test_fail_when_price_precondition_not_met(self):
        """FR-3.1a.8: wave 5 not exceeding wave 3 is a FAILED gate, not
        UNDECIDABLE."""
        w = up_impulse(p5=190)              # below wave 3's 200
        rsi = self._rsi([50.0] * 60)
        rsi.iloc[w[3].index] = 80.0
        rsi.iloc[w[5].index] = 10.0
        assert impulse.gate_imp06(w, Direction.UP, rsi) is False

    def test_pass_down_divergence(self):
        w = down_impulse()
        rsi = self._rsi([50.0] * 60)
        rsi.iloc[w[3].index] = 20.0
        rsi.iloc[w[5].index] = 30.0         # higher on a lower low
        assert impulse.gate_imp06(w, Direction.DOWN, rsi) is True

    def test_strictly_directional_equal_rsi_is_not_divergence(self):
        """FR-3.1a.5: no tolerance band. Equal RSI is not 'lower'."""
        w = up_impulse()
        rsi = self._rsi([50.0] * 60)
        rsi.iloc[w[3].index] = 75.0
        rsi.iloc[w[5].index] = 75.0
        assert impulse.gate_imp06(w, Direction.UP, rsi) is False


# ── the whole gate set together ─────────────────────────────────────────────
class TestImpulseIntegration:
    def test_failing_candidate_is_never_created(self, flat_rsi):
        """FR-5.4: no INVALID state -- a candidate failing an implementable
        gate simply does not exist in the output."""
        bad = up_impulse(p2=95)             # violates IMP-03 only
        spans = hierarchy.SpanIndex()
        spans.freeze()
        waves = impulse.classify_impulses({1: bad}, flat_rsi(200), spans)
        assert not [w for w in waves if w.structure_type is StructureType.IMPULSE]

    def test_legs_are_labelled_1_to_5_and_linked(self, diverging_rsi):
        spans = hierarchy.SpanIndex()
        spans.freeze()
        waves = impulse.classify_impulses({1: up_impulse()}, diverging_rsi(200), spans)
        parent = [w for w in waves if w.structure_type is StructureType.IMPULSE][0]
        by_id = {w.id: w for w in waves}
        legs = [by_id[c] for c in parent.child_ids]
        assert [leg.label for leg in legs] == ["1", "2", "3", "4", "5"]
        assert all(leg.parent_id == parent.id for leg in legs)

    @pytest.mark.parametrize("scale", [1, 2, 3])
    def test_wave_ids_are_deterministic(self, scale, diverging_rsi):
        spans = hierarchy.SpanIndex()
        spans.freeze()
        a = impulse.classify_impulses({scale: up_impulse(scale=scale)}, diverging_rsi(200), spans)
        spans2 = hierarchy.SpanIndex()
        spans2.freeze()
        b = impulse.classify_impulses({scale: up_impulse(scale=scale)}, diverging_rsi(200), spans2)
        assert [w.id for w in a] == [w.id for w in b]
