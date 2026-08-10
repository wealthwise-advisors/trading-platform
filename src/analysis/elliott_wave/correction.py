"""
correction.py
=============

Zigzag (5.1), generic Flat (5.2) and Running Flat (5.2.3).

  ZZ-01  3 legs, labelled A-B-C                      -- gates
  ZZ-02  waves A and C each subdivide into 5 waves
         (impulse or diagonal)                       -- gates
  ZZ-03  wave B can be ANY corrective structure      -- permissive, never gates
  ZZ-04  overall 5-3-5                               -- implied by ZZ-02 + ZZ-03
  FL-01  3 legs, 3-3-5                               -- gates
  FL-02  wave A subdivides into 3, not 5             -- gates (this is what
                                                        separates flat from zigzag)
  FLU-01 Running: wave C falls short of where wave A ended  -- gates

NOT implemented, deliberately -- these are reported as blocked, not omitted:

  * Regular Flat (FLR-01/02) -- OQ-09 and OQ-10. Wave B "terminates NEAR the
    start of wave A" and wave C "SLIGHTLY beyond the end of wave A". Neither
    "near" nor "slightly" is quantified anywhere, and the paired Fibonacci
    value is a single point (exactly 90%) with no tolerance.
  * Expanded Flat (FLE-01/02) -- OQ-10. FLE-01 alone is clean, but its second
    gate needs "SUBSTANTIALLY beyond", also unquantified. Regular and Expanded
    are separated ONLY by slightly-vs-substantially, so with OQ-10 open they
    are not distinguishable at all.
  * Triangle -- OQ-12/13. (Double/Triple Three ARE implemented, in
    combination.py, since OQ-18 was resolved by a depth cap.)

Running Flat is the one flat subtype whose non-Fibonacci gate is fully
specified by the reference (FR-3.7.3), which is why it alone ships in v1.
"""

from __future__ import annotations

from . import hierarchy
from .models import (
    LifecycleState,
    Pivot,
    StructureType,
    Wave,
)

CORRECTION_LEGS = 3
_LABELS = ("A", "B", "C")


def _wave_id(scale: int, start: int, end: int, kind: str) -> str:
    return f"s{scale}:{kind}:{start}-{end}"


def _is_five_wave(scale: int, a: Pivot, b: Pivot, spans: hierarchy.SpanIndex) -> bool | None:
    """Does [a, b] contain a five-wave structure (impulse or diagonal)?

    None at scale 1 -- no finer scale exists to inspect (D-14 recursion floor).
    """
    if scale <= 1:
        return None
    return spans.contains(scale - 1, "five_wave", a.index, b.index)


def _is_subdivided(
    pivots_by_scale: dict[int, list[Pivot]],
    scale: int,
    a: Pivot,
    b: Pivot,
) -> bool:
    """A weak 'this leg is subdivided at all' test, used for FL-02.

    FL-02 is what separates a flat from a zigzag: wave A subdivides into 3, not
    5. Combined with ``a_five is False`` at the call site, all that remains to
    establish is that wave A is subdivided at all.

    The subdivision must be looked for at the FINER scale. Looking at the same
    scale is always vacuous -- ``a`` and ``b`` are consecutive pivots there, so
    nothing ever lies strictly between them.

    Two interior pivots is the minimum consistent with a three-legged
    subdivision. The reference gives no stronger structural test for a bare
    corrective leg, so nothing stronger is invented here.
    """
    finer = pivots_by_scale.get(scale - 1)
    if not finer:
        return False
    return len(hierarchy.pivots_inside(finer, a.index, b.index)) >= 2


def gate_flu01(w: list[Pivot]) -> bool:
    """Running Flat: wave C fails to travel the full distance, falling short of
    where wave A ended.

    Wave A runs w[0]->w[1]; wave C ends at w[3]. If A fell, C must stop above
    A's low; if A rose, C must stop below A's high.
    """
    a_start, a_end, c_end = w[0].price, w[1].price, w[3].price
    return c_end > a_end if a_end < a_start else c_end < a_end


def classify_corrections(
    pivots_by_scale: dict[int, list[Pivot]],
    spans: hierarchy.SpanIndex,
) -> list[Wave]:
    """Classify zigzags and flats across every scale.

    Runs AFTER impulses and diagonals: ZZ-02 and FL-01 both need five-wave
    structures to already be registered in ``spans``.
    """
    out: list[Wave] = []

    for scale in sorted(pivots_by_scale):
        pivots = pivots_by_scale[scale]
        found: list[Wave] = []

        for w in hierarchy.windows(pivots, CORRECTION_LEGS):
            direction = hierarchy.direction_of(w)
            a_five = _is_five_wave(scale, w[0], w[1], spans)
            c_five = _is_five_wave(scale, w[2], w[3], spans)

            if a_five is None or c_five is None:
                continue                      # recursion floor -- nothing to say

            stype: StructureType | None = None
            blocked: list[str] = []

            if a_five and c_five:
                # ZZ-01..04. Wave B is permissive (ZZ-03) so it never gates.
                stype = StructureType.ZIGZAG
            elif c_five and not a_five and _is_subdivided(pivots_by_scale, scale, w[0], w[1]):
                # FL-01 / FL-02: 3-3-5 -- wave A is three waves, wave C is five.
                if gate_flu01(w):
                    stype = StructureType.FLAT_RUNNING
                else:
                    # Generic flat. Regular vs Expanded cannot be separated
                    # while OQ-09/OQ-10 are open, so the subtype is left
                    # undetermined rather than guessed.
                    #
                    # Note this stays GATED, not UNDECIDABLE: FL-01 and FL-02
                    # are both implementable and both passed, so "this is a
                    # flat" is a decided fact. Only the SUBTYPE is blocked, and
                    # blocked_by records that. Marking the whole structure
                    # UNDECIDABLE would overstate the uncertainty.
                    stype = StructureType.FLAT
                    blocked = ["FLR-01", "FLR-02", "FLE-02"]

            if stype is None:
                continue

            wave = Wave(
                id=_wave_id(scale, w[0].index, w[3].index, stype.value),
                scale=scale,
                start_pivot=w[0],
                end_pivot=w[3],
                # GATED even when `blocked` is populated -- see the note above:
                # for a flat, `blocked` records an unresolved SUBTYPE, not an
                # unresolved structure.
                state=LifecycleState.GATED,
                structure_type=stype,
                direction=direction,
                blocked_by=blocked,
            )
            for i, label in enumerate(_LABELS):
                leg = Wave(
                    id=_wave_id(scale, w[i].index, w[i + 1].index, f"{wave.id}L{label}"),
                    scale=scale,
                    start_pivot=w[i],
                    end_pivot=w[i + 1],
                    state=wave.state,
                    label=label,
                    direction=direction,
                    parent_id=wave.id,
                )
                wave.child_ids.append(leg.id)
                out.append(leg)
            found.append(wave)

        for wv in found:
            spans.add(scale, "corrective", wv.start_pivot.index, wv.end_pivot.index)
        spans.freeze()
        out.extend(found)

    return out
