"""Diagonals (LD/ED) and corrections (Zigzag, Flat, Running Flat)."""


from src.analysis.elliott_wave import correction, diagonal, hierarchy
from src.analysis.elliott_wave.models import (
    Direction, LifecycleState, Pivot, StructureType, Wave,
)

from .conftest import H, L, correction as corr_pivots, pv, up_impulse


def _host_impulse(scale=2, step=80):
    """A scale-2 impulse plus its five labelled legs, as impulse.py emits.

    ``step`` is the bar gap between host pivots. It must be wide enough that a
    finer-scale run can fit several legs inside one host leg -- a 10-bar host
    leg cannot hold a 13-leg subdivision.
    """
    w = [pv(i * step, p.price, p.kind, scale)
         for i, p in enumerate(up_impulse(scale=scale))]
    parent = Wave(id=f"s{scale}:imp:{w[0].index}-{w[5].index}", scale=scale,
                  start_pivot=w[0], end_pivot=w[5], state=LifecycleState.GATED,
                  structure_type=StructureType.IMPULSE, direction=Direction.UP)
    legs = []
    for i, label in enumerate(("1", "2", "3", "4", "5")):
        leg = Wave(id=f"s{scale}:imp{label}:{w[i].index}-{w[i+1].index}", scale=scale,
                   start_pivot=w[i], end_pivot=w[i + 1], state=LifecycleState.GATED,
                   label=label, direction=Direction.UP, parent_id=parent.id)
        parent.child_ids.append(leg.id)
        legs.append(leg)
    return w, parent, legs


def _finer_run(a: Pivot, b: Pivot, n_legs: int, scale=1):
    """A strictly alternating finer-scale run spanning [a, b] in ``n_legs`` legs.

    Two constraints the detector's own output always satisfies, and which a
    hand-built fixture must respect too:

    * **Parity.** Kind flips every step, so the final pivot's kind is fixed by
      ``n_legs``. Spanning opposite kinds (L->H) needs an ODD leg count; same
      kinds need an EVEN one. Getting this wrong produces two consecutive
      highs, which no real pivot sequence contains.
    * **Distinct indices.** There must be at least one bar per leg, or rounding
      collapses two pivots onto the same bar.

    Consequence worth knowing when sizing a fixture: because boundary parities
    alternate, every diagonal sub-wave spans an ODD number of finer legs. The
    "sub-wave is subdivided" floor of >=2 therefore means >=3 in practice, so a
    3-3-3-3-3 grouping needs at least 5 x 3 = 15 finer legs to exist at all.
    """
    span = b.index - a.index
    assert span >= n_legs, f"span {span} too narrow for {n_legs} legs"
    same_kind = a.kind is b.kind
    assert (n_legs % 2 == 0) == same_kind, (
        f"{n_legs} legs cannot run {a.kind.value}->{b.kind.value}")

    lo, hi = min(a.price, b.price), max(a.price, b.price)
    amp = max(1.0, (hi - lo) * 0.12)
    out = []
    for i in range(n_legs + 1):
        idx = a.index + (span * i) // n_legs
        kind = a.kind if i % 2 == 0 else (H if a.kind is L else L)
        base = lo + (hi - lo) * (i / n_legs)
        price = base + (amp if kind is H else -amp)
        out.append(pv(idx, price, kind, scale))
    out[0] = pv(a.index, a.price, a.kind, scale)
    out[-1] = pv(b.index, b.price, b.kind, scale)
    assert len({p.index for p in out}) == len(out), "duplicate bar indices"
    return out


# ── Leading / Ending Diagonal ───────────────────────────────────────────────
class TestDiagonalPosition:
    def test_ld01_only_in_wave_1(self):
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert structs and all(s.structure_type is StructureType.LEADING_DIAGONAL
                               for s in structs)

    def test_ed01_only_in_wave_5(self):
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[4], w[5], 15)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert structs and all(s.structure_type is StructureType.ENDING_DIAGONAL
                               for s in structs)

    def test_no_diagonal_in_wave_2_3_or_4(self):
        """LD-01/ED-01 restrict hosts to waves 1 and 5."""
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[1], w[2], 15)      # wave 2's span
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        assert not [x for x in found if x.structure_type is not None]

    def test_no_hosts_means_no_diagonals(self):
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, notes = diagonal.classify_diagonals({1: up_impulse()}, [], spans)
        assert found == [] and notes == []


class TestDiagonalOverlapNeverGates:
    def test_tr3_overlapping_waves_1_and_4_still_classify(self):
        """TR-3. The reference is explicit that overlap 'is not a condition'.
        This exact geometry would fail a plain impulse's IMP-05."""
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        # Force the diagonal's own wave 1 and wave 4 to overlap in price.
        # This exact geometry would fail a plain impulse's IMP-05.
        for i in range(1, len(finer) - 1):
            finer[i] = pv(finer[i].index,
                          300.0 if finer[i].kind is H else 90.0,
                          finer[i].kind, 1)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert structs, "overlap must not prevent classification"
        assert any(s.measurements.get("waves_1_4_overlap") for s in structs)

    def test_overlap_is_recorded_as_a_measurement(self):
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        for s in [x for x in found if x.structure_type is not None]:
            assert "waves_1_4_overlap" in s.measurements


class TestDiagonalGroupingOQ25:
    def test_every_diagonal_carries_the_oq25_caveat(self):
        """OQ-25 is unresolved, so the caveat must travel with the data."""
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert structs
        assert all(s.blocked_by == ["OQ-25"] for s in structs)

    def test_grouping_no_longer_requires_exactly_five_finer_legs(self):
        """The rev-2 fix: a host subdividing into 15 finer legs must still be
        groupable into 5 sub-waves. Rev 1, which demanded exactly 5, found
        nothing here."""
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        assert len(finer) - 1 == 15
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        assert [x for x in found if x.structure_type is not None]

    def test_enumeration_cap_is_respected_and_reported(self):
        """A very finely subdivided host produces many valid groupings. The cap
        must bound them AND say so -- never truncate silently."""
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 41)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, notes = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert len(structs) <= diagonal.MAX_GROUPINGS_PER_HOST
        if len(structs) == diagonal.MAX_GROUPINGS_PER_HOST:
            assert any("cap" in n for n in notes), "truncation must be reported"

    def test_sub_waves_alternate_direction(self):
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        by_id = {x.id: x for x in found}
        for s in [x for x in found if x.structure_type is not None]:
            kinds = [by_id[c].end_pivot.kind for c in s.child_ids]
            for a, b in zip(kinds, kinds[1:]):
                assert a != b

    def test_variant_recorded(self):
        w, parent, legs = _host_impulse()
        finer = _finer_run(w[0], w[1], 15)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found, _ = diagonal.classify_diagonals({1: finer, 2: w}, [parent] + legs, spans)
        for s in [x for x in found if x.structure_type is not None]:
            assert s.measurements["subdivision_variant"] in ("5-3-5-3-5", "3-3-3-3-3")


# ── Zigzag / Flat / Running Flat ────────────────────────────────────────────
class TestCorrections:
    def _setup(self, a_five: bool, c_five: bool, a_subdivided: bool = True,
               p3=130):
        w = corr_pivots(p3=p3)
        w = [pv(p.index, p.price, p.kind, 2) for p in w]
        spans = hierarchy.SpanIndex()
        if a_five:
            spans.add(1, "five_wave", w[0].index, w[1].index)
        if c_five:
            spans.add(1, "five_wave", w[2].index, w[3].index)
        spans.freeze()
        finer = []
        if a_subdivided:
            finer = _finer_run(w[0], w[1], 5)
        return w, spans, {1: finer, 2: w}

    def test_zz01_04_zigzag_needs_five_wave_a_and_c(self):
        w, spans, by_scale = self._setup(a_five=True, c_five=True)
        found = correction.classify_corrections(by_scale, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert structs and structs[0].structure_type is StructureType.ZIGZAG

    def test_zz02_fails_without_five_wave_c(self):
        w, spans, by_scale = self._setup(a_five=True, c_five=False)
        found = correction.classify_corrections(by_scale, spans)
        assert not [x for x in found if x.structure_type is StructureType.ZIGZAG]

    def test_fl02_flat_requires_a_to_be_three_not_five(self):
        """FL-02 is exactly what separates a flat from a zigzag."""
        w, spans, by_scale = self._setup(a_five=False, c_five=True, p3=130)
        found = correction.classify_corrections(by_scale, spans)
        structs = [x for x in found if x.structure_type is not None]
        assert structs
        assert structs[0].structure_type in (StructureType.FLAT,
                                             StructureType.FLAT_RUNNING)

    def test_flat_not_created_when_a_is_unsubdivided(self):
        w, spans, by_scale = self._setup(a_five=False, c_five=True,
                                         a_subdivided=False)
        found = correction.classify_corrections(by_scale, spans)
        assert not [x for x in found if x.structure_type is not None]

    def test_flu01_running_flat_c_falls_short_of_a(self):
        # A falls 200 -> 150; C ends at 160, short of 150 -> running
        w = corr_pivots(p3=160)
        assert correction.gate_flu01(w) is True

    def test_flu01_fails_when_c_travels_past_a(self):
        w = corr_pivots(p3=130)            # C goes beyond A's low
        assert correction.gate_flu01(w) is False

    def test_generic_flat_is_gated_with_subtype_blocked(self):
        """A generic flat is a DECIDED flat -- only its subtype is blocked, so
        it must be GATED with blocked_by recording the unresolved subtype."""
        w, spans, by_scale = self._setup(a_five=False, c_five=True, p3=130)
        found = correction.classify_corrections(by_scale, spans)
        flats = [x for x in found if x.structure_type is StructureType.FLAT]
        assert flats
        assert flats[0].state is LifecycleState.GATED
        assert set(flats[0].blocked_by) == {"FLR-01", "FLR-02", "FLE-02"}

    def test_recursion_floor_yields_nothing_at_scale_1(self):
        """D-14: no finer scale, so the five-wave gates cannot be evaluated."""
        w = corr_pivots()
        spans = hierarchy.SpanIndex()
        spans.freeze()
        found = correction.classify_corrections({1: w}, spans)
        assert found == []

    def test_legs_labelled_A_B_C(self):
        w, spans, by_scale = self._setup(a_five=True, c_five=True)
        found = correction.classify_corrections(by_scale, spans)
        parent = [x for x in found if x.structure_type is not None][0]
        by_id = {x.id: x for x in found}
        assert [by_id[c].label for c in parent.child_ids] == ["A", "B", "C"]
