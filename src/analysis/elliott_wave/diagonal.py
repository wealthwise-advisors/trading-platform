"""
diagonal.py
===========

Leading Diagonal (LD-*) and Ending Diagonal (ED-*), reference sections 3.3/3.4.

  LD-01  appears as wave 1 of an impulse, or wave A of a zigzag   -- gates
  LD-03  subdivision is 5-3-5-3-5 or 3-3-3-3-3                     -- gates
  ED-01  appears as wave 5 of an impulse, or wave C of a zigzag   -- gates
  ED-03  subdivision is 3-3-3-3-3 or 5-3-5-3-5                     -- gates
  LD-02 / ED-02  wave 1/4 overlap + wedge shape                    -- see below

OVERLAP MUST NEVER GATE
-----------------------
The reference is unusually explicit: "overlap between wave 1 and 4 is NOT a
condition, it may or may not happen". Overlap is measured and recorded, and a
diagonal with overlapping waves 1 and 4 -- which would fail a plain impulse's
IMP-05 -- still classifies. TR-3 guards this, because the natural instinct when
reading IMP-05 is to apply the same check here.

WEDGE SHAPE IS NOT IMPLEMENTED
------------------------------
"Wedge shape" is never quantified (OQ-15, open). No geometry is invented.

SUB-WAVE GROUPING (revised 2026-08-10)
--------------------------------------
Rev 1 required the host leg's finer subdivision to land on EXACTLY 5 legs, so a
diagonal was only visible when the pivot ladder happened to quantise that way
(~18% of legs). That is an artifact of the ladder, not a requirement of the
reference: a genuine diagonal's five sub-waves need not align 1:1 with any
detection threshold.

Rev 2 groups finer legs into 5 sub-waves. The grouping is constrained ONLY by
things the reference actually states:

  * Alternation -- a 5-wave motive structure alternates direction, so the four
    interior sub-wave boundaries must alternate high/low. Since finer pivots
    already alternate, this fixes each boundary's parity.
  * LD-03 / ED-03 shape -- either
      5-3-5-3-5 : sub-waves 1/3/5 each contain a five-wave structure, and
                  sub-waves 2/4 contain none;
      3-3-3-3-3 : no sub-wave contains a five-wave structure, and every
                  sub-wave is subdivided (>= 2 finer legs), consistent with
                  GEN-06 "corrective waves move in three".
    Either variant classifies; neither is a fallback.

Every grouping satisfying those constraints is emitted as its own alternate.
Nothing ranks or prunes between them -- FR-2.4 (selection between overlapping
candidates) is UNDEFINED, and inventing a preference here would be exactly the
kind of guess this build refuses to make.

>>> NEW OPEN QUESTION: OQ-25 <<<
The reference constrains the SHAPE of a diagonal's subdivision but never
defines how detector-scale legs combine into an Elliott sub-wave. "Sub-wave 3
is a five-wave structure" is checked here as "the finer scale registers an
impulse inside that span", which is a reading, not a stated rule. Recorded in
validation.BLOCKED_RULES and in the docs rather than presented as settled.

V1 SCOPE LIMITATION
-------------------
Hosts are impulse waves 1/5 only. Zigzag waves A/C are also valid hosts per
LD-01/ED-01, but corrections are classified after diagonals in the pipeline, so
diagonals hosted inside a zigzag are not detected in v1.
"""

from __future__ import annotations

from . import hierarchy
from .models import (
    LifecycleState,
    Pivot,
    StructureType,
    Wave,
)

DIAGONAL_SUBWAVES = 5
_LABELS = ("1", "2", "3", "4", "5")

# Engineering bound on grouping enumeration (FR-2.6 requires bounded
# enumeration; the reference says nothing about search limits). If a host leg
# yields more groupings than this, the excess is dropped AND reported -- never
# silently truncated.
MAX_GROUPINGS_PER_HOST = 64


def _wave_id(scale: int, start: int, end: int, kind: str) -> str:
    return f"s{scale}:{kind}:{start}-{end}"


def waves_1_and_4_overlap(boundaries: list[Pivot]) -> bool:
    """LD-02 / ED-02 -- measured for the record, NEVER used as a gate."""
    lo1, hi1 = sorted((boundaries[0].price, boundaries[1].price))
    lo4, hi4 = sorted((boundaries[3].price, boundaries[4].price))
    return lo4 <= hi1 and lo1 <= hi4


def _enumerate_groupings(span: list[Pivot]) -> list[list[int]]:
    """All ways to cut ``span`` into 5 direction-alternating sub-waves.

    ``span`` is the finer-scale pivot run whose ends coincide with the host
    leg's ends. Returns lists of 4 interior positions within ``span``.

    Alternation is the only constraint applied here: because the finer pivots
    already alternate high/low, a boundary at an odd offset from the start is
    always the opposite kind to one at an even offset, so valid cut sets are
    exactly those with strictly increasing positions of alternating parity.
    """
    n = len(span)
    if n < 6:                      # need at least 5 legs to cut into 5
        return []
    out: list[list[int]] = []
    # sub-wave 1 ends at odd parity, 2 at even, 3 at odd, 4 at even
    for i1 in range(1, n - 4, 2):
        for i2 in range(i1 + 1, n - 3, 2):
            for i3 in range(i2 + 1, n - 2, 2):
                for i4 in range(i3 + 1, n - 1, 2):
                    out.append([i1, i2, i3, i4])
                    if len(out) > MAX_GROUPINGS_PER_HOST * 8:
                        return out
    return out


def _shape_variant(
    span: list[Pivot],
    cuts: list[int],
    finer_scale: int,
    spans: hierarchy.SpanIndex,
) -> str | None:
    """Classify a grouping against LD-03 / ED-03. None if it matches neither."""
    idx = [0] + cuts + [len(span) - 1]
    sub = [(span[idx[i]], span[idx[i + 1]]) for i in range(DIAGONAL_SUBWAVES)]
    legs = [idx[i + 1] - idx[i] for i in range(DIAGONAL_SUBWAVES)]

    five = [spans.contains(finer_scale, "five_wave", a.index, b.index) for a, b in sub]

    # 5-3-5-3-5: sub-waves 1/3/5 are five-wave, 2/4 are not.
    if five[0] and five[2] and five[4] and not five[1] and not five[3]:
        return "5-3-5-3-5"
    # 3-3-3-3-3: none is a five-wave, and every sub-wave is subdivided.
    if not any(five) and all(n >= 2 for n in legs):
        return "3-3-3-3-3"
    return None


def classify_diagonals(
    pivots_by_scale: dict[int, list[Pivot]],
    impulses: list[Wave],
    spans: hierarchy.SpanIndex,
) -> tuple[list[Wave], list[str]]:
    """Find diagonals occupying wave 1 or wave 5 of an already-found impulse.

    Returns (waves, notes). Notes record any enumeration truncation so a capped
    search is visible rather than silently partial.
    """
    out: list[Wave] = []
    notes: list[str] = []

    by_id = {w.id: w for w in impulses}
    hosts: list[tuple[int, str, Pivot, Pivot]] = []
    for parent in impulses:
        if parent.structure_type is not StructureType.IMPULSE:
            continue
        for cid in parent.child_ids:
            leg = by_id.get(cid)
            if leg is None or leg.label not in ("1", "5"):
                continue
            hosts.append((parent.scale, leg.label, leg.start_pivot, leg.end_pivot))

    for host_scale, label, a, b in hosts:
        finer_scale = host_scale - 1
        finer = pivots_by_scale.get(finer_scale)
        if not finer:
            # Recursion floor (D-14): no finer scale to subdivide into, so
            # LD-03/ED-03 cannot be evaluated. Nothing is emitted rather than
            # a guessed pass or fail.
            continue

        span = [p for p in finer if a.index <= p.index <= b.index]
        if len(span) < 6 or span[0].index != a.index or span[-1].index != b.index:
            continue

        stype = (StructureType.LEADING_DIAGONAL if label == "1"
                 else StructureType.ENDING_DIAGONAL)

        groupings = _enumerate_groupings(span)
        accepted = 0
        for cuts in groupings:
            variant = _shape_variant(span, cuts, finer_scale, spans)
            if variant is None:
                continue
            if accepted >= MAX_GROUPINGS_PER_HOST:
                notes.append(
                    f"Diagonal grouping search for {stype.value} at bars "
                    f"[{a.index},{b.index}] hit the {MAX_GROUPINGS_PER_HOST}-alternate "
                    f"cap; further valid groupings were not emitted."
                )
                break
            accepted += 1

            idx = [0] + cuts + [len(span) - 1]
            boundaries = [span[i] for i in idx]
            wave = Wave(
                id=_wave_id(finer_scale, a.index, b.index,
                            f"{'ld' if label == '1' else 'ed'}#{accepted}"),
                scale=finer_scale,
                start_pivot=boundaries[0],
                end_pivot=boundaries[-1],
                state=LifecycleState.GATED,
                structure_type=stype,
                direction=hierarchy.direction_of(span),
                measurements={
                    # recorded, never gating (LD-02 / ED-02)
                    "waves_1_4_overlap": waves_1_and_4_overlap(boundaries),
                    "subdivision_variant": variant,
                    "finer_legs_spanned": len(span) - 1,
                },
                blocked_by=["OQ-25"],
            )
            for i, sub_label in enumerate(_LABELS):
                leg = Wave(
                    id=_wave_id(finer_scale, boundaries[i].index,
                                boundaries[i + 1].index, f"{wave.id}L{sub_label}"),
                    scale=finer_scale,
                    start_pivot=boundaries[i],
                    end_pivot=boundaries[i + 1],
                    state=wave.state,
                    label=sub_label,
                    direction=wave.direction,
                    parent_id=wave.id,
                )
                wave.child_ids.append(leg.id)
                out.append(leg)
            out.append(wave)

    for wv in [w for w in out if w.structure_type is not None]:
        spans.add(wv.scale, "five_wave", wv.start_pivot.index, wv.end_pivot.index)
    spans.freeze()
    return out, notes
